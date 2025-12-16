"""
Position-aware anti-correlation architecture for NFL.

Prevents correlated failures in multi-leg parlays.
"""

from typing import List, Tuple
from hollersports.nfl.types import Projection, NFLGameRow, Side, Market


def check_leg_compatibility(
    leg1: Projection,
    leg2: Projection,
    all_data: List[NFLGameRow],
) -> Tuple[bool, str]:
    """
    Check if two legs are compatible (anti-correlated).

    Rules:
    1. Different games: always compatible
    2. Same player: incompatible
    3. Same team, both HIGHER: incompatible (correlated volume)
    4. Same team, both LOWER: weak compatibility (correlated suppression)
    5. Same position, same team, volume markets: incompatible
    6. Opposing teams: compatible
    7. QB + pass catchers on same team (both HIGHER): compatible

    Args:
        leg1: First projection
        leg2: Second projection
        all_data: Full dataset for context lookup

    Returns:
        (compatible, reason) tuple
    """
    # Rule 1: Different games always compatible
    if leg1.game_id != leg2.game_id:
        return True, "different games"

    # Rule 2: Same player incompatible
    if leg1.player_id == leg2.player_id:
        return False, "same player"

    # Get team assignments
    team1 = _get_player_team(leg1.player_id, leg1.game_id, all_data)
    team2 = _get_player_team(leg2.player_id, leg2.game_id, all_data)

    if team1 is None or team2 is None:
        # Can't determine teams: reject for safety
        return False, "unknown team assignment"

    # Rule 6: Opposing teams compatible
    if team1 != team2:
        return True, "opposing teams"

    # Same team checks
    pos1 = leg1.position
    pos2 = leg2.position
    market1 = leg1.market
    market2 = leg2.market
    side1 = leg1.side
    side2 = leg2.side

    # Rule 3: Same team, both HIGHER on volume markets
    if side1 == Side.HIGHER and side2 == Side.HIGHER:
        # Check if both are volume markets (not yardage)
        volume_markets = {Market.RECEPTIONS, Market.TARGETS, Market.RUSH_ATT}

        if market1 in volume_markets and market2 in volume_markets:
            # Exception: QB + pass catchers compatible (QB throwing to them)
            if _is_qb_to_receiver_pair(pos1, pos2):
                return True, "QB to receiver (compatible)"

            # Otherwise incompatible
            return False, "same team both overs (correlated volume)"

    # Rule 4: Same team, both LOWER
    if side1 == Side.LOWER and side2 == Side.LOWER:
        # Weak compatibility: both betting on suppression
        return True, "same team both unders (weak correlation acceptable)"

    # Rule 5: Same position, same team, volume markets
    if pos1 == pos2:
        volume_markets = {Market.RECEPTIONS, Market.TARGETS, Market.RUSH_ATT}
        if market1 in volume_markets and market2 in volume_markets:
            return False, "same position same team (competing for touches)"

    # Default: compatible
    return True, "no correlation conflict detected"


def build_anti_correlated_slate(
    candidates: List[Projection],
    all_data: List[NFLGameRow],
    target_size: int = 5,
) -> List[Projection]:
    """
    Build anti-correlated slate from candidates.

    Greedy algorithm:
    1. Sort candidates by quality (confidence * p_hit)
    2. Add best candidate
    3. For each remaining, check compatibility with all selected
    4. Add if compatible, skip if not
    5. Stop at target_size

    Args:
        candidates: All candidate projections (sorted by quality)
        all_data: Full dataset for team lookup
        target_size: Target slate size

    Returns:
        List of compatible projections
    """
    if not candidates:
        return []

    # Sort by quality
    sorted_candidates = sorted(
        candidates,
        key=lambda p: p.confidence * p.p_hit,
        reverse=True,
    )

    slate = []

    for candidate in sorted_candidates:
        if len(slate) >= target_size:
            break

        # Check compatibility with all existing legs
        compatible = True
        for existing_leg in slate:
            is_compatible, reason = check_leg_compatibility(candidate, existing_leg, all_data)
            if not is_compatible:
                compatible = False
                break

        if compatible:
            slate.append(candidate)

    return slate


def _get_player_team(
    player_id: str,
    game_id: str,
    all_data: List[NFLGameRow],
) -> str:
    """Get player's team for a specific game."""
    for row in all_data:
        if row.player_id == player_id and row.game_id == game_id:
            return row.team
    return None


def _is_qb_to_receiver_pair(pos1: str, pos2: str) -> bool:
    """Check if positions are QB + receiver (compatible)."""
    receivers = {"WR", "TE", "RB"}

    if pos1 == "QB" and pos2 in receivers:
        return True
    if pos2 == "QB" and pos1 in receivers:
        return True

    return False
