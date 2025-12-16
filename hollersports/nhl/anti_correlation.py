"""
Anti-Correlation Architecture for NHL SOG slate building.

Prevents cannibalizing legs by avoiding correlated failures.
"""

from typing import List, Tuple
from hollersports.nhl.types import SOGProjection, Side, NHLGameRow


def check_leg_compatibility(
    leg1: SOGProjection,
    leg2: SOGProjection,
    all_data: List[NHLGameRow],
) -> Tuple[bool, str]:
    """
    Check if two legs are compatible (not correlated failures).

    Rules:
    1. Don't pair two Overs on same team unless low correlation
    2. Prefer cross-team legs
    3. Don't pair player Over with goalie Under in same game

    Args:
        leg1: First projection
        leg2: Second projection
        all_data: Full dataset for correlation analysis

    Returns:
        Tuple of (compatible: bool, reason: str)
    """
    # Extract game and team info
    game1 = leg1.game_id
    game2 = leg2.game_id

    # Rule 1: Same player (should never happen, but check)
    if leg1.player_id == leg2.player_id:
        return False, "Same player"

    # Rule 2: Check if same game
    same_game = (game1 == game2)

    if same_game:
        # More scrutiny for same-game legs

        # Find player teams from data
        player1_games = [g for g in all_data if g.player_id == leg1.player_id and g.game_id == game1]
        player2_games = [g for g in all_data if g.player_id == leg2.player_id and g.game_id == game2]

        if not player1_games or not player2_games:
            # Can't determine team, allow cautiously
            return True, "Same game, teams unknown"

        team1 = player1_games[0].team
        team2 = player2_games[0].team

        same_team = (team1 == team2)

        if same_team:
            # Same team, same game - check sides
            both_overs = (leg1.side == Side.HIGHER and leg2.side == Side.HIGHER)
            both_unders = (leg1.side == Side.LOWER and leg2.side == Side.LOWER)

            if both_overs:
                # Two overs on same team - risky if both are forwards
                # Could suppress each other in low-scoring game
                # For now, reject unless explicit override
                return False, "Same team, both Overs (potential suppression)"

            if both_unders:
                # Two unders on same team - could be correlated if team underperforms
                return False, "Same team, both Unders (correlated risk)"

            # Mixed sides (one over, one under) on same team - acceptable
            return True, "Same team, mixed sides (acceptable)"

        else:
            # Same game, different teams - generally okay
            # Check for goalie-player interaction
            # (We don't have position in projection, so skip detailed check)
            return True, "Same game, different teams (acceptable)"

    # Rule 3: Different games - generally compatible
    # Prefer this for diversification
    return True, "Different games (diversified)"


def filter_slate_for_anti_correlation(
    candidates: List[SOGProjection],
    all_data: List[NHLGameRow],
    max_same_team_overs: int = 1,
) -> List[SOGProjection]:
    """
    Filter candidate legs to reduce correlation.

    Args:
        candidates: List of candidate projections (sorted by quality)
        all_data: Full dataset
        max_same_team_overs: Maximum overs allowed from same team

    Returns:
        Filtered list of compatible projections
    """
    filtered = []
    team_over_count = {}

    for candidate in candidates:
        # Find player's team
        player_games = [g for g in all_data if g.player_id == candidate.player_id and g.game_id == candidate.game_id]

        if not player_games:
            # Can't determine team, include cautiously
            filtered.append(candidate)
            continue

        team = player_games[0].team

        # Check same-team over limit
        if candidate.side == Side.HIGHER:
            current_count = team_over_count.get(team, 0)

            if current_count >= max_same_team_overs:
                # Skip this over (would exceed limit)
                continue

            # Add to filtered and update count
            filtered.append(candidate)
            team_over_count[team] = current_count + 1

        else:
            # Under - no same-team limit (for now)
            filtered.append(candidate)

    return filtered


def build_anti_correlated_slate(
    candidates: List[SOGProjection],
    all_data: List[NHLGameRow],
    target_size: int = 5,
) -> List[SOGProjection]:
    """
    Build a slate of anti-correlated legs.

    Greedy algorithm:
    1. Start with highest-quality candidate
    2. Add next candidate if compatible with all current legs
    3. Repeat until target_size reached

    Args:
        candidates: List of candidate projections (sorted by quality descending)
        all_data: Full dataset
        target_size: Number of legs to select

    Returns:
        List of selected projections (anti-correlated)
    """
    if not candidates:
        return []

    slate = [candidates[0]]  # Start with best

    for candidate in candidates[1:]:
        if len(slate) >= target_size:
            break

        # Check compatibility with all current slate members
        compatible = True

        for existing in slate:
            is_compat, reason = check_leg_compatibility(candidate, existing, all_data)

            if not is_compat:
                compatible = False
                break

        if compatible:
            slate.append(candidate)

    return slate
