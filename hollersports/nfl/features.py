"""
Feature engineering for NFL SCMF.

Computes role stability metrics: target share, route participation, snap share, rush share.
"""

from typing import List, Optional
import numpy as np

from hollersports.nfl.types import NFLGameRow, FeatureSet


def build_features(
    player_id: str,
    game_id: str,
    player_history: List[NFLGameRow],
    all_data: List[NFLGameRow],
) -> Optional[FeatureSet]:
    """
    Build feature set for a player-game.

    Args:
        player_id: Player identifier
        game_id: Target game identifier
        player_history: Historical games for this player (sorted chronologically)
        all_data: Full dataset (for team context)

    Returns:
        FeatureSet or None if insufficient data
    """
    if len(player_history) < 3:
        return None  # Insufficient history

    # Get position from most recent game
    position = player_history[-1].position

    # Extract last 5 games (or fewer if not available)
    recent_games = player_history[-5:]

    last5_targets = [g.targets for g in recent_games]
    last5_receptions = [g.receptions for g in recent_games]
    last5_routes = [g.routes if g.routes is not None else 0 for g in recent_games]
    last5_snaps = [g.snaps for g in recent_games]
    last5_rush_att = [g.rushing_attempts for g in recent_games]

    # Season medians (all available history)
    season_targets_median = float(np.median([g.targets for g in player_history]))
    season_receptions_median = float(np.median([g.receptions for g in player_history]))
    season_routes_median = float(
        np.median([g.routes for g in player_history if g.routes is not None])
    ) if any(g.routes is not None for g in player_history) else 0.0
    season_snaps_median = float(np.median([g.snaps for g in player_history]))

    # Compute share metrics
    target_share_proxy = _compute_target_share(recent_games, all_data)
    route_participation = _compute_route_participation(recent_games)
    rush_share = _compute_rush_share(recent_games, all_data, position)
    snap_share = _compute_snap_share(recent_games, all_data)

    # Stability flags
    role_stable = _check_role_stability(last5_targets, last5_routes, last5_snaps)
    volatility_flag = _check_volatility(last5_targets, last5_receptions)

    return FeatureSet(
        player_id=player_id,
        game_id=game_id,
        position=position,
        last5_targets=last5_targets,
        last5_receptions=last5_receptions,
        last5_routes=last5_routes,
        last5_snaps=last5_snaps,
        last5_rush_att=last5_rush_att,
        season_targets_median=season_targets_median,
        season_receptions_median=season_receptions_median,
        season_routes_median=season_routes_median,
        season_snaps_median=season_snaps_median,
        target_share_proxy=target_share_proxy,
        route_participation=route_participation,
        rush_share=rush_share,
        snap_share=snap_share,
        role_stable=role_stable,
        volatility_flag=volatility_flag,
    )


def _compute_target_share(
    recent_games: List[NFLGameRow],
    all_data: List[NFLGameRow],
) -> float:
    """
    Compute approximate target share.

    Share = player_targets / team_targets (last 3 games avg)
    """
    if len(recent_games) < 3:
        return 0.0

    player_targets = sum(g.targets for g in recent_games[-3:])

    # Get team totals for same games
    team_targets_total = 0
    for game in recent_games[-3:]:
        team_total = sum(
            row.targets for row in all_data
            if row.game_id == game.game_id and row.team == game.team
        )
        team_targets_total += team_total

    if team_targets_total == 0:
        return 0.0

    return player_targets / team_targets_total


def _compute_route_participation(recent_games: List[NFLGameRow]) -> float:
    """
    Compute route participation rate.

    routes / snaps (avg last 3 games)
    """
    if len(recent_games) < 3:
        return 0.0

    valid_games = [
        g for g in recent_games[-3:]
        if g.routes is not None and g.snaps > 0
    ]

    if not valid_games:
        return 0.0

    rates = [g.routes / g.snaps for g in valid_games]
    return float(np.mean(rates))


def _compute_rush_share(
    recent_games: List[NFLGameRow],
    all_data: List[NFLGameRow],
    position: str,
) -> float:
    """
    Compute rush share for RBs.

    For non-RBs, returns 0.
    """
    if position != "RB":
        return 0.0

    if len(recent_games) < 3:
        return 0.0

    player_rushes = sum(g.rushing_attempts for g in recent_games[-3:])

    # Get team rush totals
    team_rushes_total = 0
    for game in recent_games[-3:]:
        team_total = sum(
            row.rushing_attempts for row in all_data
            if row.game_id == game.game_id and row.team == game.team
        )
        team_rushes_total += team_total

    if team_rushes_total == 0:
        return 0.0

    return player_rushes / team_rushes_total


def _compute_snap_share(
    recent_games: List[NFLGameRow],
    all_data: List[NFLGameRow],
) -> float:
    """
    Compute snap share.

    player_snaps / max_team_snaps (proxy for offensive snaps)
    """
    if len(recent_games) < 3:
        return 0.0

    player_snaps = sum(g.snaps for g in recent_games[-3:])

    # Use max snaps on team as proxy for total offensive snaps
    team_max_snaps = 0
    for game in recent_games[-3:]:
        max_snaps_in_game = max(
            (row.snaps for row in all_data
             if row.game_id == game.game_id and row.team == game.team),
            default=0
        )
        team_max_snaps += max_snaps_in_game

    if team_max_snaps == 0:
        return 0.0

    return player_snaps / team_max_snaps


def _check_role_stability(
    last5_targets: List[int],
    last5_routes: List[int],
    last5_snaps: List[int],
) -> bool:
    """
    Check if player role is stable.

    Stable if:
    - Coefficient of variation < 0.35 for targets
    - Snaps std < 15
    """
    if len(last5_targets) < 4:
        return False

    # Targets CV
    targets_mean = np.mean(last5_targets)
    if targets_mean == 0:
        return False

    targets_cv = np.std(last5_targets) / targets_mean

    # Snaps std
    snaps_std = np.std(last5_snaps)

    return targets_cv < 0.35 and snaps_std < 15


def _check_volatility(
    last5_targets: List[int],
    last5_receptions: List[int],
) -> bool:
    """
    Check for high volatility.

    Flag if:
    - Targets range > 8
    - Receptions range > 6
    """
    if len(last5_targets) < 4:
        return False

    targets_range = max(last5_targets) - min(last5_targets)
    receptions_range = max(last5_receptions) - min(last5_receptions)

    return targets_range > 8 or receptions_range > 6
