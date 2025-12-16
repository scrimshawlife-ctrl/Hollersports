"""
Script State Probability Tree for NFL.

Converts vegas spread/total into game flow state probabilities.
Simple deterministic model for LEADING/TRAILING/NEUTRAL/TWO_MINUTE time shares.
"""

from typing import Dict, Optional
from hollersports.nfl.types import ScriptState


def compute_script_priors(
    vegas_spread: Optional[float],
    vegas_total: Optional[float] = None,
) -> Dict[ScriptState, float]:
    """
    Compute script state probabilities from vegas context.

    Args:
        vegas_spread: Point spread (negative = team favored)
        vegas_total: Game total (optional, unused in base model)

    Returns:
        Dict mapping ScriptState to probability [0, 1], sum = 1.0

    Model:
        - neutral_share = clamp(0.55 - abs(spread)*0.02, 0.25, 0.65)
        - leading_share = if favored: clamp(0.20 + spread*0.02, 0.05, 0.55) else 0.10
        - trailing_share = if underdog: clamp(0.20 + abs(spread)*0.02, 0.05, 0.55) else 0.10
        - two_minute_share = 0.05 (fixed)
        - Normalize to sum = 1.0
    """
    if vegas_spread is None:
        # No vegas context: assume balanced neutral script
        return {
            ScriptState.NEUTRAL: 0.70,
            ScriptState.LEADING: 0.10,
            ScriptState.TRAILING: 0.10,
            ScriptState.TWO_MINUTE: 0.10,
        }

    spread = float(vegas_spread)

    # Neutral share: decreases as spread magnitude increases
    neutral_share = _clamp(0.55 - abs(spread) * 0.02, 0.25, 0.65)

    # Leading/trailing shares depend on favored/underdog status
    is_favored = spread < 0

    if is_favored:
        # Favored team: more leading time
        leading_share = _clamp(0.20 + abs(spread) * 0.02, 0.05, 0.55)
        trailing_share = 0.10
    else:
        # Underdog team: more trailing time
        leading_share = 0.10
        trailing_share = _clamp(0.20 + abs(spread) * 0.02, 0.05, 0.55)

    # Two-minute drill: fixed small share
    two_minute_share = 0.05

    # Build raw priors
    priors = {
        ScriptState.NEUTRAL: neutral_share,
        ScriptState.LEADING: leading_share,
        ScriptState.TRAILING: trailing_share,
        ScriptState.TWO_MINUTE: two_minute_share,
    }

    # Normalize to sum = 1.0
    total = sum(priors.values())
    normalized = {state: prob / total for state, prob in priors.items()}

    return normalized


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def get_script_modifier(
    state: ScriptState,
    market: str,
    position: str,
) -> float:
    """
    Get script state modifier for market projections.

    Simple position × market × script multipliers.

    Args:
        state: Script state (LEADING/TRAILING/NEUTRAL/TWO_MINUTE)
        market: Market string (RECEPTIONS, RUSH_ATT, etc.)
        position: Position (WR, TE, RB, QB)

    Returns:
        Multiplicative modifier (typically 0.8 - 1.2)

    Examples:
        - RB RUSH_ATT when LEADING: 1.15 (more rushing)
        - WR RECEPTIONS when TRAILING: 1.10 (more passing)
        - TE TARGETS when TWO_MINUTE: 1.05 (checkdowns)
    """
    market_upper = market.upper()
    position_upper = position.upper()

    # Neutral script: no modifier
    if state == ScriptState.NEUTRAL:
        return 1.0

    # Leading script: run-heavy
    if state == ScriptState.LEADING:
        if position_upper == "RB":
            if "RUSH" in market_upper:
                return 1.15  # More rushing attempts
            elif "REC" in market_upper or "TARGET" in market_upper:
                return 0.90  # Fewer pass targets
        elif position_upper in ("WR", "TE"):
            if "REC" in market_upper or "TARGET" in market_upper:
                return 0.90  # Less passing
        elif position_upper == "QB":
            if "PASS" in market_upper:
                return 0.90  # Fewer pass attempts
        return 1.0

    # Trailing script: pass-heavy
    if state == ScriptState.TRAILING:
        if position_upper == "RB":
            if "RUSH" in market_upper:
                return 0.85  # Fewer rushing attempts
            elif "REC" in market_upper or "TARGET" in market_upper:
                return 1.10  # More pass targets to RBs
        elif position_upper in ("WR", "TE"):
            if "REC" in market_upper or "TARGET" in market_upper:
                return 1.10  # More passing
        elif position_upper == "QB":
            if "PASS" in market_upper:
                return 1.10  # More pass attempts
        return 1.0

    # Two-minute script: quick passing, checkdowns
    if state == ScriptState.TWO_MINUTE:
        if position_upper == "RB":
            if "REC" in market_upper or "TARGET" in market_upper:
                return 1.05  # Checkdowns to RBs
        elif position_upper == "TE":
            if "REC" in market_upper or "TARGET" in market_upper:
                return 1.05  # Checkdowns to TEs
        elif position_upper == "WR":
            if "REC" in market_upper or "TARGET" in market_upper:
                return 1.00  # Neutral for WRs
        return 1.0

    return 1.0


def compute_script_weighted_median(
    neutral_median: float,
    script_priors: Dict[ScriptState, float],
    market: str,
    position: str,
) -> float:
    """
    Compute script-weighted median projection.

    Args:
        neutral_median: Base median under neutral script
        script_priors: Probability of each script state
        market: Market string
        position: Position string

    Returns:
        Weighted median accounting for script probabilities

    Formula:
        mu = sum(P(script) * modifier(script) * neutral_median)
    """
    weighted_sum = 0.0

    for state, prob in script_priors.items():
        modifier = get_script_modifier(state, market, position)
        weighted_sum += prob * modifier * neutral_median

    return weighted_sum
