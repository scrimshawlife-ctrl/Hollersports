"""
ABX-Core: Scorer-Under Eligibility Gate

Deterministic, typed, testable module for filtering PTS-UNDER props based on
multi-signal suppression indicators.

Objective:
    Reduce miss-rate on scorer-under bets by only allowing picks when ≥2
    suppression signals are present (arena elasticity, coach distribution,
    opponent compression, blowout risk, teammate correlation).

Usage:
    from abraxas.modules.scorer_under_gate import backtest, GateConfig

    df, report = backtest("legs.csv", GateConfig())
    print(report)
    df.to_csv("legs_with_gate.csv", index=False)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
import pandas as pd
import hashlib
import json

# -----------------------------
# Provenance / Determinism
# -----------------------------

def stable_hash_dict(d: Dict) -> str:
    """
    Generate a deterministic hash from a dictionary.

    Args:
        d: Dictionary to hash

    Returns:
        16-character hex string (first 16 chars of SHA-256)
    """
    payload = json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]

# -----------------------------
# Config
# -----------------------------

@dataclass(frozen=True)
class GateConfig:
    """
    Configuration for the Scorer-Under gate.

    All thresholds are deterministic and version-controlled. Changing any value
    will change the config hash, enabling full reproducibility.
    """

    # Signal thresholds (tuneable, but deterministic)
    blowout_spread_abs: float = 8.0  # abs(spread) >= 8 => blowout risk
    opp_def_rating_strong: float = 112.0  # lower is better defense; use if you have it
    opp_tov_rate_high: float = 14.5       # higher => more compression
    arena_elasticity_low_quantile: float = 0.35  # bottom 35% = "low elasticity"
    coach_distribution_low_quantile: float = 0.35

    # Gate rule
    min_signals_required: int = 2

    # Column names (so you can adapt quickly)
    col_date: str = "date"
    col_player: str = "player"
    col_team: str = "team"
    col_opp: str = "opponent"
    col_home: str = "home"
    col_arena: str = "arena"
    col_prop: str = "prop_type"
    col_pick: str = "pick"
    col_line: str = "line"
    col_result: str = "result"
    col_hit: str = "hit"
    col_spread: str = "spread"
    col_total: str = "total"

# -----------------------------
# Feature engineering
# -----------------------------

def compute_hit(row: pd.Series, cfg: GateConfig) -> int:
    """
    Compute whether a prop leg hit (1) or missed (0).

    Args:
        row: DataFrame row containing line, result, and pick
        cfg: Gate configuration with column names

    Returns:
        1 if hit, 0 if miss

    Raises:
        ValueError: If pick is not 'higher' or 'lower'
    """
    line = float(row[cfg.col_line])
    actual = float(row[cfg.col_result])
    pick = str(row[cfg.col_pick]).lower().strip()
    if pick == "higher":
        return int(actual > line)
    if pick == "lower":
        return int(actual < line)
    raise ValueError(f"Unknown pick: {pick}")

def arena_elasticity_proxy(df_games: pd.DataFrame, cfg: GateConfig) -> pd.Series:
    """
    Proxy for 'arena elasticity':
    Use arena-level average total points (team+opp) from your logged games.
    Higher avg total => more elastic scoring environment.
    Requires columns: arena, total (or can approximate from sum of results if you log team scores).

    Args:
        df_games: DataFrame with game-level data
        cfg: Gate configuration

    Returns:
        Series of normalized arena elasticity values (0..1)
    """
    if cfg.col_arena not in df_games.columns or cfg.col_total not in df_games.columns:
        # If not available, return neutral mid-value so it won't trigger LOW.
        return pd.Series([0.5] * len(df_games), index=df_games.index)

    arena_means = df_games.groupby(cfg.col_arena)[cfg.col_total].mean()
    # Normalize to 0..1
    mn, mx = float(arena_means.min()), float(arena_means.max())
    if mx == mn:
        arena_norm = arena_means * 0.0 + 0.5
    else:
        arena_norm = (arena_means - mn) / (mx - mn)

    return df_games[cfg.col_arena].map(arena_norm).fillna(0.5)

def coach_distribution_proxy(df_legs: pd.DataFrame, cfg: GateConfig) -> pd.Series:
    """
    Proxy for coach distribution philosophy using team-level dispersion of PTS legs outcomes.
    If you have coach names, you can map team->coach. Otherwise we approximate from
    how concentrated scoring legs are across players (crude but usable with enough logs).

    Args:
        df_legs: DataFrame with all prop legs
        cfg: Gate configuration

    Returns:
        Series of normalized coach concentration values (0..1)
    """
    # compute per-team "concentration" from PTS legs: std dev of player average points
    pts = df_legs[df_legs[cfg.col_prop].str.upper() == "PTS"].copy()
    if pts.empty:
        return pd.Series([0.5] * len(df_legs), index=df_legs.index)

    player_means = pts.groupby([cfg.col_team, cfg.col_player])[cfg.col_result].mean().reset_index()
    team_disp = player_means.groupby(cfg.col_team)[cfg.col_result].std().fillna(0.0)

    # Normalize 0..1 where higher dispersion => more concentrated usage => "less distributed"
    mn, mx = float(team_disp.min()), float(team_disp.max())
    if mx == mn:
        team_norm = team_disp * 0.0 + 0.5
    else:
        team_norm = (team_disp - mn) / (mx - mn)

    return df_legs[cfg.col_team].map(team_norm).fillna(0.5)

def opponent_compression_proxy(df_games: pd.DataFrame, cfg: GateConfig) -> pd.Series:
    """
    Proxy for opponent defensive compression.
    If you have opponent defensive rating or opponent TOV rate, use it.
    Otherwise neutral.

    Args:
        df_games: DataFrame with game-level data
        cfg: Gate configuration

    Returns:
        Series of normalized opponent compression values (0..1)
    """
    # Prefer opp_def_rating if exists
    if "opp_def_rating" in df_games.columns:
        # Lower def rating = stronger defense => more compression
        dr = df_games["opp_def_rating"].astype(float)
        # invert + normalize
        inv = dr.max() - dr
        mn, mx = float(inv.min()), float(inv.max())
        return ((inv - mn) / (mx - mn)).fillna(0.5) if mx != mn else inv * 0.0 + 0.5

    if "opp_tov_rate" in df_games.columns:
        tov = df_games["opp_tov_rate"].astype(float)
        mn, mx = float(tov.min()), float(tov.max())
        return ((tov - mn) / (mx - mn)).fillna(0.5) if mx != mn else tov * 0.0 + 0.5

    return pd.Series([0.5] * len(df_games), index=df_games.index)

# -----------------------------
# Gate logic
# -----------------------------

@dataclass(frozen=True)
class GateDecision:
    """
    Deterministic gate decision with full provenance.

    Attributes:
        eligible: Whether the prop passes the gate (True = allow)
        signals_true: Count of suppression signals that fired
        reasons: Dictionary of individual signal results
        provenance: Deterministic hash for reproducibility
    """
    eligible: bool
    signals_true: int
    reasons: Dict[str, bool]
    provenance: str

def scorer_under_gate(row: pd.Series, cfg: GateConfig) -> GateDecision:
    """
    Evaluate whether a PTS-UNDER prop is eligible based on suppression signals.

    Gate rule: Allow if ≥ min_signals_required suppression signals are true.

    Signals:
        1. Arena elasticity LOW (restrictive scoring environment)
        2. Coach distribution LOW (concentrated usage => fewer scorers)
        3. Opponent defensive compression HIGH (strong defense limiting volume)
        4. Blowout risk MODERATE+ (garbage time, benched starters)
        5. Teammate PRA spike correlation (optional, requires multi-leg logs)

    Args:
        row: DataFrame row with normalized features and metadata
        cfg: Gate configuration

    Returns:
        GateDecision with eligibility, signal count, reasons, and provenance hash
    """
    # Only applies to PTS lower
    prop = str(row[cfg.col_prop]).upper().strip()
    pick = str(row[cfg.col_pick]).lower().strip()
    if not (prop == "PTS" and pick == "lower"):
        reasons = {"not_applicable": True}
        return GateDecision(True, 0, reasons, stable_hash_dict({"cfg": cfg.__dict__, "na": True}))

    # Signals (booleans)
    # Arena: low elasticity => arena_elasticity_norm <= quantile threshold
    arena_norm = float(row.get("arena_elasticity_norm", 0.5))
    arena_low = arena_norm <= float(row.get("arena_elasticity_low_cut", 0.35))

    # Coach distribution: low distribution => high concentration norm >= cut? We define "low distribution"
    # as "more concentrated", i.e., coach_concentration_norm >= (1 - quantile)
    coach_conc = float(row.get("coach_concentration_norm", 0.5))
    coach_low_dist = coach_conc >= float(row.get("coach_low_dist_cut", 0.65))

    # Opponent compression: high compression norm >= cut
    opp_comp = float(row.get("opp_compression_norm", 0.5))
    opp_comp_high = opp_comp >= float(row.get("opp_comp_high_cut", 0.65))

    # Blowout risk: abs(spread) >= threshold, if spread exists
    spread = row.get(cfg.col_spread, None)
    if spread is None or (isinstance(spread, float) and pd.isna(spread)):
        blowout = False
    else:
        blowout = abs(float(spread)) >= cfg.blowout_spread_abs

    # Teammate correlation (optional)
    teammate_corr = bool(row.get("teammate_pra_suppression", False))

    reasons = {
        "arena_low_elasticity": arena_low,
        "coach_low_distribution": coach_low_dist,
        "opponent_compression_high": opp_comp_high,
        "blowout_risk": blowout,
        "teammate_pra_suppression": teammate_corr,
    }
    signals_true = sum(1 for v in reasons.values() if v)

    eligible = signals_true >= cfg.min_signals_required
    prov = stable_hash_dict({"cfg": cfg.__dict__, "reasons": reasons, "signals": signals_true})

    return GateDecision(eligible, signals_true, reasons, prov)

# -----------------------------
# Backtest runner
# -----------------------------

def backtest(csv_path: str, cfg: GateConfig) -> Tuple[pd.DataFrame, Dict]:
    """
    Run a complete backtest of the Scorer-Under gate on historical prop legs.

    Process:
        1. Load legs CSV
        2. Compute hit outcomes if missing
        3. Engineer proxy features (arena elasticity, coach distribution, etc.)
        4. Apply gate to each PTS-UNDER leg
        5. Generate comparison report (baseline vs filtered hit rates)

    Args:
        csv_path: Path to CSV with historical prop legs
        cfg: Gate configuration

    Returns:
        Tuple of (DataFrame with gate decisions, summary report dict)

    Report keys:
        - rows_total: Total rows in CSV
        - pts_lower_rows: Number of PTS-UNDER legs
        - baseline_pts_lower_hit_rate: Hit rate without gate
        - filtered_pts_lower_rows: Number of legs passing gate
        - filtered_pts_lower_hit_rate: Hit rate with gate applied
        - blocked_pts_lower_rows: Number of legs blocked by gate
        - volume_retained: Fraction of volume retained (0..1)
        - cfg_hash: Deterministic hash of configuration
        - cuts: Quantile thresholds computed from data
    """
    df = pd.read_csv(csv_path)

    # Handle empty dataframe
    if df.empty:
        # Add required columns for empty case
        df["gate_eligible"] = []
        df["gate_signals"] = []
        df["gate_provenance"] = []
        df["gate_reasons"] = []
        if cfg.col_hit not in df.columns:
            df[cfg.col_hit] = []

        report = {
            "rows_total": 0,
            "pts_lower_rows": 0,
            "baseline_pts_lower_hit_rate": float("nan"),
            "filtered_pts_lower_rows": 0,
            "filtered_pts_lower_hit_rate": float("nan"),
            "blocked_pts_lower_rows": 0,
            "volume_retained": float("nan"),
            "cfg_hash": stable_hash_dict(cfg.__dict__),
            "cuts": {"arena_low": float("nan"), "coach_low_dist": float("nan"), "opp_comp_high": float("nan")},
        }
        return df, report

    # Normalize key columns
    df[cfg.col_prop] = df[cfg.col_prop].astype(str)
    df[cfg.col_pick] = df[cfg.col_pick].astype(str)

    # Compute hit if missing
    if cfg.col_hit not in df.columns:
        df[cfg.col_hit] = df.apply(lambda r: compute_hit(r, cfg), axis=1)

    # Build game-level frame for arena/opponent proxies (use rows as-is; this is a light proxy)
    df_games = df.copy()

    # Compute proxy norms + cuts (quantile-based, deterministic)
    df_games["arena_elasticity_norm"] = arena_elasticity_proxy(df_games, cfg)
    df_games["coach_concentration_norm"] = coach_distribution_proxy(df, cfg)  # team-based proxy
    df_games["opp_compression_norm"] = opponent_compression_proxy(df_games, cfg)

    arena_cut = float(df_games["arena_elasticity_norm"].quantile(cfg.arena_elasticity_low_quantile))
    coach_cut = 1.0 - float(df_games["coach_concentration_norm"].quantile(cfg.coach_distribution_low_quantile))
    opp_cut = float(df_games["opp_compression_norm"].quantile(1.0 - cfg.coach_distribution_low_quantile))

    # Attach cuts (row-wise)
    df_games["arena_elasticity_low_cut"] = arena_cut
    df_games["coach_low_dist_cut"] = coach_cut
    df_games["opp_comp_high_cut"] = opp_cut

    # Apply gate
    decisions: List[GateDecision] = [scorer_under_gate(r, cfg) for _, r in df_games.iterrows()]
    df_games["gate_eligible"] = [d.eligible for d in decisions]
    df_games["gate_signals"] = [d.signals_true for d in decisions]
    df_games["gate_provenance"] = [d.provenance for d in decisions]
    df_games["gate_reasons"] = [json.dumps(d.reasons, sort_keys=True) for d in decisions]

    # Report: only PTS lowers are "subject" legs
    is_pts_lower = (df_games[cfg.col_prop].str.upper() == "PTS") & (df_games[cfg.col_pick].str.lower() == "lower")
    subject = df_games[is_pts_lower].copy()

    baseline_hit = float(subject[cfg.col_hit].mean()) if len(subject) else float("nan")
    filtered = subject[subject["gate_eligible"]].copy()
    filtered_hit = float(filtered[cfg.col_hit].mean()) if len(filtered) else float("nan")

    report = {
        "rows_total": int(len(df_games)),
        "pts_lower_rows": int(len(subject)),
        "baseline_pts_lower_hit_rate": baseline_hit,
        "filtered_pts_lower_rows": int(len(filtered)),
        "filtered_pts_lower_hit_rate": filtered_hit,
        "blocked_pts_lower_rows": int(len(subject) - len(filtered)),
        "volume_retained": float(len(filtered) / len(subject)) if len(subject) else float("nan"),
        "cfg_hash": stable_hash_dict(cfg.__dict__),
        "cuts": {"arena_low": arena_cut, "coach_low_dist": coach_cut, "opp_comp_high": opp_cut},
    }

    return df_games, report

# -----------------------------
# Minimal tests
# -----------------------------

def _test_gate_basic():
    """Basic smoke test for gate logic."""
    cfg = GateConfig()
    row = pd.Series({
        "prop_type": "PTS",
        "pick": "lower",
        "arena_elasticity_norm": 0.10,
        "arena_elasticity_low_cut": 0.35,
        "coach_concentration_norm": 0.90,
        "coach_low_dist_cut": 0.65,
        "opp_compression_norm": 0.20,
        "opp_comp_high_cut": 0.65,
        "spread": 2.0,
    })
    d = scorer_under_gate(row, cfg)
    assert d.eligible is True
    assert d.signals_true >= 2
    print(f"  ✓ Gate decision: eligible={d.eligible}, signals={d.signals_true}")

def _test_hash_determinism():
    """Test that hashing is deterministic."""
    cfg1 = GateConfig()
    cfg2 = GateConfig()
    hash1 = stable_hash_dict(cfg1.__dict__)
    hash2 = stable_hash_dict(cfg2.__dict__)
    assert hash1 == hash2
    print(f"  ✓ Hash determinism: {hash1}")

if __name__ == "__main__":
    print("ABX Scorer-Under Gate: Running tests...")
    _test_hash_determinism()
    _test_gate_basic()
    print("✓ All tests passed.")
