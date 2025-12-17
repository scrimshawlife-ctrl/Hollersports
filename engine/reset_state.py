# FILE: HollerSports/engine/reset_state.py
# ABX-Core / SEED-compliant: deterministic, provenance-embedded, no mock placeholders.
# Purpose: hard-reset per-slate state so no prior slate leakage occurs.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import hashlib
import json
import time


# -----------------------------
# Provenance / determinism
# -----------------------------

def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _now_utc_epoch() -> int:
    # Determinism note: timestamps are provenance only; never used for decision logic.
    return int(time.time())


# -----------------------------
# Core state objects
# -----------------------------

@dataclass(frozen=True)
class SlateIdentity:
    slate_id: str                      # e.g. "NBA_2025-12-17_EVENING"
    sport: str                         # "NBA", "NFL", "NHL"...
    as_of_utc_epoch: int               # provenance only
    source_fingerprint: str            # hash of inputs used to define slate (games list + lines snapshot)


@dataclass
class MarketLineSnapshot:
    """
    Snapshot of market lines (props/alt lines) used for this run.
    This is what prevents accidentally using older lines when you re-run.
    """
    provider: str                      # e.g. "PrizePicks", "Underdog", etc.
    captured_utc_epoch: int            # provenance only
    lines: Dict[str, Any]              # keyed by canonical market key (see below)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fingerprint", _sha256(_stable_json({
            "provider": self.provider,
            "lines": self.lines,
        })))


@dataclass
class GameContextCache:
    """
    Per-game contextual modifiers that should be recomputed per slate:
    venue, travel, rest, coaching pace, rotation stability, etc.
    These should adjust distribution width or minor mean shifts—never override raw player priors blindly.
    """
    by_game_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    fingerprint: str = field(default_factory=str)

    def recompute_fingerprint(self) -> None:
        self.fingerprint = _sha256(_stable_json(self.by_game_id))


@dataclass
class CalibrationMemory:
    """
    Stores adaptation / streak adjustment artifacts, but MUST NOT bleed across slates
    unless explicitly opted-in via a controlled merge.
    """
    enabled: bool = True
    # e.g. {"NBA:player:123": {"fatigue_delta": 0.12, "tempo_skew": -0.04, ...}}
    adjustments: Dict[str, Dict[str, float]] = field(default_factory=dict)
    fingerprint: str = field(default_factory=str)

    def recompute_fingerprint(self) -> None:
        self.fingerprint = _sha256(_stable_json(self.adjustments))


@dataclass
class RunState:
    """
    The single source of truth for one slate run.
    Everything that can drift must be either reset or proven to be slate-scoped.
    """
    slate: SlateIdentity
    market: MarketLineSnapshot

    # Computed caches (slate-scoped)
    game_context: GameContextCache = field(default_factory=GameContextCache)

    # Simulation artifacts (slate-scoped)
    simulations: Dict[str, Any] = field(default_factory=dict)     # e.g. Monte Carlo outputs keyed by market key
    picks: List[Dict[str, Any]] = field(default_factory=list)     # chosen legs with probabilities, ROI, etc.

    # Optional adaptation memory (must be guarded)
    calibration: CalibrationMemory = field(default_factory=CalibrationMemory)

    # Provenance ledger
    provenance: Dict[str, Any] = field(default_factory=dict)


# -----------------------------
# Canonical market keying
# -----------------------------

def make_market_key(
    sport: str,
    game_id: str,
    player_id: str,
    market: str,
    line: float,
    side: str,
) -> str:
    """
    Stable key to identify a specific prop/leg.
    """
    payload = {
        "sport": sport,
        "game_id": game_id,
        "player_id": player_id,
        "market": market,   # "PTS", "AST", "PRA", "3PM", etc
        "line": float(line),
        "side": side.upper(),  # "OVER"/"UNDER"
    }
    return _sha256(_stable_json(payload))


# -----------------------------
# Reset / init entrypoints
# -----------------------------

def compute_slate_source_fingerprint(
    games_payload: Dict[str, Any],
    lines_payload: Dict[str, Any],
    provider: str,
) -> str:
    """
    Fingerprint the slate inputs (games + current lines snapshot).
    Use this to prove the run is based on current data.
    """
    return _sha256(_stable_json({
        "games": games_payload,
        "provider": provider,
        "lines": lines_payload,
    }))


def init_new_slate_state(
    *,
    slate_id: str,
    sport: str,
    provider: str,
    games_payload: Dict[str, Any],
    lines_payload: Dict[str, Any],
    keep_calibration_memory: bool = False,
    prior_calibration: Optional[CalibrationMemory] = None,
) -> RunState:
    """
    Create a brand-new RunState for a slate.
    By default: NO carry-over. If keep_calibration_memory=True, we merge in a controlled way.
    """

    src_fp = compute_slate_source_fingerprint(games_payload, lines_payload, provider)

    slate = SlateIdentity(
        slate_id=slate_id,
        sport=sport,
        as_of_utc_epoch=_now_utc_epoch(),   # provenance only
        source_fingerprint=src_fp,
    )

    market = MarketLineSnapshot(
        provider=provider,
        captured_utc_epoch=_now_utc_epoch(),  # provenance only
        lines=lines_payload,
    )

    state = RunState(slate=slate, market=market)

    # Provenance: declare reset rules explicitly
    state.provenance["reset_policy"] = {
        "no_slate_bleed": True,
        "keep_calibration_memory": bool(keep_calibration_memory),
        "calibration_merge_mode": "explicit_merge" if keep_calibration_memory else "discard",
    }
    state.provenance["inputs"] = {
        "games_fingerprint": _sha256(_stable_json(games_payload)),
        "lines_fingerprint": market.fingerprint,
        "slate_source_fingerprint": src_fp,
        "provider": provider,
    }
    state.provenance["created_utc_epoch"] = _now_utc_epoch()

    # Handle calibration memory (guarded)
    if keep_calibration_memory and prior_calibration and prior_calibration.enabled:
        # Controlled merge: only copy scalar adjustments, never picks/sims.
        state.calibration.enabled = True
        state.calibration.adjustments = json.loads(_stable_json(prior_calibration.adjustments))
        state.calibration.recompute_fingerprint()
        state.provenance["calibration_loaded"] = {
            "fingerprint": state.calibration.fingerprint,
            "count": len(state.calibration.adjustments),
        }
    else:
        # Hard reset: no prior adjustments
        state.calibration.enabled = True
        state.calibration.adjustments = {}
        state.calibration.recompute_fingerprint()
        state.provenance["calibration_loaded"] = {"fingerprint": state.calibration.fingerprint, "count": 0}

    # Ensure empty caches
    state.game_context.by_game_id = {}
    state.game_context.recompute_fingerprint()
    state.simulations = {}
    state.picks = []

    return state


def assert_state_matches_inputs(
    state: RunState,
    *,
    games_payload: Dict[str, Any],
    lines_payload: Dict[str, Any],
    provider: str,
) -> None:
    """
    Guardrail: prevents accidental re-use of an old state with new inputs.
    Call at the top of every rerun/backtest entrypoint.
    """
    expected = compute_slate_source_fingerprint(games_payload, lines_payload, provider)

    if state.slate.source_fingerprint != expected:
        raise RuntimeError(
            "Slate state mismatch: inputs do not match the state's source_fingerprint. "
            "You are likely leaking prior slate context. Create a new RunState via init_new_slate_state()."
        )

    # Also assert the market snapshot matches
    market_fp = _sha256(_stable_json({"provider": provider, "lines": lines_payload}))
    if state.market.fingerprint != market_fp:
        raise RuntimeError(
            "Market snapshot mismatch: lines/provider differ from the state's MarketLineSnapshot. "
            "Create a new RunState via init_new_slate_state()."
        )


def hard_reset_runtime_artifacts(state: RunState) -> None:
    """
    Clears computed artifacts that must never persist across recalcs within the same slate
    unless explicitly intended.
    """
    state.game_context.by_game_id = {}
    state.game_context.recompute_fingerprint()
    state.simulations = {}
    state.picks = []
    state.provenance["hard_reset_runtime_artifacts_utc_epoch"] = _now_utc_epoch()


# -----------------------------
# Optional: controlled merge helpers
# -----------------------------

def merge_calibration_delta(
    base: CalibrationMemory,
    delta: Dict[str, Dict[str, float]],
    *,
    allow_new_keys: bool = True,
) -> CalibrationMemory:
    """
    Deterministic merge for calibration adjustments. Use for streak adjustment rollups.
    """
    merged = CalibrationMemory(enabled=base.enabled)
    merged.adjustments = json.loads(_stable_json(base.adjustments))

    for k, v in delta.items():
        if (k not in merged.adjustments) and not allow_new_keys:
            continue
        merged.adjustments.setdefault(k, {})
        for metric, val in v.items():
            merged.adjustments[k][metric] = float(val)

    merged.recompute_fingerprint()
    return merged
