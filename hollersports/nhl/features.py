"""
Feature engineering for NHL SOG projections.

Computes deterministic features from historical game data.
"""

from typing import List, Dict, Optional
import numpy as np

from hollersports.nhl.types import NHLGameRow, FeatureSet


# Default weights for last-5 weighted average
DEFAULT_LAST5_WEIGHTS = [0.35, 0.25, 0.18, 0.12, 0.10]


def compute_weighted_average(values: List[float], weights: Optional[List[float]] = None) -> float:
    """
    Compute weighted average of recent values.

    Args:
        values: List of values (most recent first)
        weights: Optional weight vector (must match length)

    Returns:
        Weighted average
    """
    if not values:
        return 0.0

    if weights is None:
        weights = DEFAULT_LAST5_WEIGHTS[:len(values)]
    elif len(weights) < len(values):
        # Pad weights if needed
        weights = list(weights) + [0.0] * (len(values) - len(weights))

    # Normalize weights
    total_weight = sum(weights[:len(values)])
    if total_weight == 0:
        return float(np.mean(values))

    weighted_sum = sum(v * w for v, w in zip(values, weights[:len(values)]))
    return weighted_sum / total_weight


def build_features(
    player_id: str,
    game_id: str,
    player_history: List[NHLGameRow],
    all_data: List[NHLGameRow],
    target_game: NHLGameRow,
) -> FeatureSet:
    """
    Build feature set for a player-game projection.

    Args:
        player_id: Player identifier
        game_id: Target game identifier
        player_history: Historical games for this player (sorted by date, most recent first)
        all_data: Full dataset for opponent/position computations
        target_game: The game being projected

    Returns:
        FeatureSet with computed features
    """
    # Extract SOG values
    sog_history = [g.sog for g in player_history]

    # Last-5 weighted average
    last5_sog = sog_history[:5]
    last5_sog_weighted = compute_weighted_average(last5_sog)

    # Season median
    season_sog_median = float(np.median(sog_history)) if sog_history else 0.0

    # Last-10 for volatility check
    last10_sog_list = sog_history[:10]

    # TOI features
    toi_history = [g.toi_minutes for g in player_history]
    toi_last5 = toi_history[:5]
    toi_last5_median = float(np.median(toi_last5)) if toi_last5 else 0.0
    toi_season_median = float(np.median(toi_history)) if toi_history else 0.0

    # PP share
    pp_share = None
    pp_share_last5 = None

    if target_game.pp_toi_minutes is not None:
        # Compute PP share for this player
        pp_history = [
            g.pp_toi_minutes / g.toi_minutes if g.pp_toi_minutes and g.toi_minutes > 0 else 0.0
            for g in player_history
            if g.pp_toi_minutes is not None
        ]

        if pp_history:
            pp_share = float(np.mean(pp_history))
            pp_share_last5 = float(np.mean(pp_history[:5])) if len(pp_history) >= 5 else pp_share

    # Opponent position SOG allowed
    opponent = target_game.opponent
    position = target_game.position

    opponent_pos_sog_allowed = compute_opponent_position_sog_allowed(
        opponent, position, all_data
    )

    # Role stability check (preliminary)
    role_stable = False
    if toi_season_median >= 14.0:  # Minimum TOI threshold
        if toi_last5_median > 0:
            toi_ratio = toi_last5_median / toi_season_median
            if 0.85 <= toi_ratio <= 1.15:  # Within +/- 15%
                role_stable = True

    # Volatility flag
    volatility_flag = False
    if len(last10_sog_list) >= 5:
        std_last10 = float(np.std(last10_sog_list))
        if std_last10 > 2.0:  # High volatility threshold
            volatility_flag = True

    return FeatureSet(
        player_id=player_id,
        game_id=game_id,
        last5_sog_weighted=last5_sog_weighted,
        season_sog_median=season_sog_median,
        last10_sog_list=last10_sog_list,
        toi_last5_median=toi_last5_median,
        toi_season_median=toi_season_median,
        pp_share=pp_share,
        pp_share_last5=pp_share_last5,
        opponent_pos_sog_allowed=opponent_pos_sog_allowed,
        is_home=target_game.is_home,
        role_stable=role_stable,
        volatility_flag=volatility_flag,
    )


def compute_opponent_position_sog_allowed(
    opponent: str,
    position: str,
    all_data: List[NHLGameRow],
) -> float:
    """
    Compute average SOG allowed by opponent to this position.

    Args:
        opponent: Opponent team identifier
        position: Player position (F, D, G)
        all_data: Full dataset

    Returns:
        Average SOG allowed to position by this opponent
    """
    # Find games where this opponent played (as opponent of others)
    relevant_games = [
        g for g in all_data
        if g.opponent == opponent and g.position == position
    ]

    if not relevant_games:
        # Fallback: league average for position
        all_position_sog = [g.sog for g in all_data if g.position == position]
        return float(np.mean(all_position_sog)) if all_position_sog else 3.0

    sog_vs_opponent = [g.sog for g in relevant_games]
    return float(np.mean(sog_vs_opponent))


def compute_team_avg_sog(team: str, all_data: List[NHLGameRow]) -> float:
    """
    Compute team's average SOG (for pace proxy if needed).

    Args:
        team: Team identifier
        all_data: Full dataset

    Returns:
        Team average SOG
    """
    team_games = [g for g in all_data if g.team == team]

    if not team_games:
        return 30.0  # League average fallback

    total_sog = sum(g.sog for g in team_games)
    return total_sog / len(team_games) if team_games else 30.0
