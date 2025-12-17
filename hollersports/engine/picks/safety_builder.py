# FILE: hollersports/engine/picks/safety_builder.py
# Ultra-safe 5-leg builder with strict no-bleed constraints

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class Leg:
    """A single prop leg candidate."""
    market_key: str
    sport: str
    game_id: str
    player_id: str
    market_type: str  # "PTS", "REB", "AST", etc.
    side: str         # "OVER" or "UNDER"
    line: float
    p_hit: float      # Probability of hitting
    corr_penalty: float  # Correlation penalty
    sigma: float      # Standard deviation / variance measure
    edge: float       # Expected edge
    constraints: Tuple[str, ...]  # Additional constraint tags
    pool_fingerprint: str


@dataclass(frozen=True)
class CandidatePool:
    """Immutable pool of candidate legs."""
    slate_id: str
    provider: str
    legs: Tuple[Leg, ...]
    fingerprint: str


@dataclass(frozen=True)
class SafetyConfig:
    """Configuration for ultra-safe pick building."""
    min_p_hit: float
    max_same_player: int


def build_ultra_safe_5_leg_from_core_3(
    core3: List[Leg],
    pool: CandidatePool,
    cfg: SafetyConfig,
) -> Dict[str, Any]:
    """
    Build a 5-leg parlay from 3 core legs + 2 additions from pool.

    Enforces:
    - No duplicate market_key
    - No more than max_same_player legs from same player
    - All additions meet min_p_hit threshold

    Args:
        core3: Exactly 3 core legs (already validated)
        pool: Candidate pool containing all available legs
        cfg: Safety configuration

    Returns:
        Dictionary with "legs" key containing list of 5 leg dicts

    Raises:
        ValueError if cannot build valid 5-leg
    """
    if len(core3) != 3:
        raise ValueError(f"Expected exactly 3 core legs, got {len(core3)}")

    # Track used market keys and player counts
    used_keys = {leg.market_key for leg in core3}
    player_counts: Dict[str, int] = {}
    for leg in core3:
        player_counts[leg.player_id] = player_counts.get(leg.player_id, 0) + 1

    # Find valid additions from pool
    additions: List[Leg] = []
    for leg in pool.legs:
        # Skip if already used
        if leg.market_key in used_keys:
            continue

        # Skip if below probability threshold
        if leg.p_hit < cfg.min_p_hit:
            continue

        # Check player limit
        current_count = player_counts.get(leg.player_id, 0)
        if current_count >= cfg.max_same_player:
            continue

        # Valid addition candidate
        additions.append(leg)

        # Stop when we have enough
        if len(additions) >= 2:
            break

    if len(additions) < 2:
        raise ValueError(
            f"Could not find 2 valid additions. "
            f"Found {len(additions)} candidates meeting constraints."
        )

    # Build final 5-leg output
    all_legs = core3 + additions[:2]

    # Convert to dict format for output
    legs_dicts = [
        {
            "market_key": leg.market_key,
            "sport": leg.sport,
            "game_id": leg.game_id,
            "player_id": leg.player_id,
            "market_type": leg.market_type,
            "side": leg.side,
            "line": leg.line,
            "p_hit": leg.p_hit,
            "corr_penalty": leg.corr_penalty,
            "sigma": leg.sigma,
            "edge": leg.edge,
        }
        for leg in all_legs
    ]

    return {"legs": legs_dicts}
