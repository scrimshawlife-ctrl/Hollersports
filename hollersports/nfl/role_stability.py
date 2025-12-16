"""
Position-specific role stability gates for NFL.

Filters players with unstable usage patterns.
"""

from typing import List
import numpy as np

from hollersports.nfl.types import FeatureSet, RoleStabilityResult, Market


def check_role_stability(
    features: FeatureSet,
    market: Market,
    config: dict,
) -> RoleStabilityResult:
    """
    Check role stability for player.

    Position-specific gates:
    - WR: routes > 20/game, target share > 15%, low volatility
    - TE: routes > 15/game, target share > 12%
    - RB: snap share > 40%, rush share > 25% OR target share > 10%
    - QB: snap share > 95% (starter check)

    Args:
        features: Player features
        market: Target market
        config: Configuration dict

    Returns:
        RoleStabilityResult with pass/fail and diagnostics
    """
    position = features.position
    flags = []

    # Position-specific checks
    if position == "WR":
        result = _check_wr_stability(features, market, config, flags)
    elif position == "TE":
        result = _check_te_stability(features, market, config, flags)
    elif position == "RB":
        result = _check_rb_stability(features, market, config, flags)
    elif position == "QB":
        result = _check_qb_stability(features, market, config, flags)
    else:
        # Unknown position: reject
        flags.append(f"unknown_position:{position}")
        result = RoleStabilityResult(
            passed=False,
            role_score=0.0,
            position=position,
            flags=flags,
        )

    return result


def _check_wr_stability(
    features: FeatureSet,
    market: Market,
    config: dict,
    flags: List[str],
) -> RoleStabilityResult:
    """Check WR role stability."""
    # Minimum routes
    min_routes = config.get("wr_min_routes", 20)
    routes_avg = np.mean(features.last5_routes) if features.last5_routes else 0

    routes_stable = routes_avg >= min_routes
    if not routes_stable:
        flags.append(f"wr_routes_low:{routes_avg:.1f}<{min_routes}")

    # Minimum target share
    min_target_share = config.get("wr_min_target_share", 0.15)
    target_share_stable = features.target_share_proxy >= min_target_share
    if not target_share_stable:
        flags.append(f"wr_target_share_low:{features.target_share_proxy:.2f}<{min_target_share}")

    # Volatility check
    low_volatility = not features.volatility_flag
    if features.volatility_flag:
        flags.append("wr_high_volatility")

    # Snap share check
    min_snap_share = config.get("wr_min_snap_share", 0.50)
    snaps_stable = features.snap_share >= min_snap_share
    if not snaps_stable:
        flags.append(f"wr_snap_share_low:{features.snap_share:.2f}<{min_snap_share}")

    # Compute role score
    role_score = 0.0
    if routes_stable:
        role_score += 0.3
    if target_share_stable:
        role_score += 0.4
    if low_volatility:
        role_score += 0.2
    if snaps_stable:
        role_score += 0.1

    # Pass if role_score >= 0.60
    min_role_score = config.get("min_role_score", 0.60)
    passed = role_score >= min_role_score

    if not passed:
        flags.append(f"wr_role_score_low:{role_score:.2f}<{min_role_score}")

    return RoleStabilityResult(
        passed=passed,
        role_score=role_score,
        position="WR",
        routes_stable=routes_stable,
        snaps_stable=snaps_stable,
        targets_stable=target_share_stable,
        flags=flags,
    )


def _check_te_stability(
    features: FeatureSet,
    market: Market,
    config: dict,
    flags: List[str],
) -> RoleStabilityResult:
    """Check TE role stability."""
    # Lower thresholds than WR
    min_routes = config.get("te_min_routes", 15)
    routes_avg = np.mean(features.last5_routes) if features.last5_routes else 0

    routes_stable = routes_avg >= min_routes
    if not routes_stable:
        flags.append(f"te_routes_low:{routes_avg:.1f}<{min_routes}")

    # Minimum target share (lower than WR)
    min_target_share = config.get("te_min_target_share", 0.12)
    target_share_stable = features.target_share_proxy >= min_target_share
    if not target_share_stable:
        flags.append(f"te_target_share_low:{features.target_share_proxy:.2f}<{min_target_share}")

    # Snap share
    min_snap_share = config.get("te_min_snap_share", 0.45)
    snaps_stable = features.snap_share >= min_snap_share
    if not snaps_stable:
        flags.append(f"te_snap_share_low:{features.snap_share:.2f}<{min_snap_share}")

    # Role score
    role_score = 0.0
    if routes_stable:
        role_score += 0.35
    if target_share_stable:
        role_score += 0.35
    if snaps_stable:
        role_score += 0.30

    min_role_score = config.get("min_role_score", 0.60)
    passed = role_score >= min_role_score

    if not passed:
        flags.append(f"te_role_score_low:{role_score:.2f}<{min_role_score}")

    return RoleStabilityResult(
        passed=passed,
        role_score=role_score,
        position="TE",
        routes_stable=routes_stable,
        snaps_stable=snaps_stable,
        targets_stable=target_share_stable,
        flags=flags,
    )


def _check_rb_stability(
    features: FeatureSet,
    market: Market,
    config: dict,
    flags: List[str],
) -> RoleStabilityResult:
    """Check RB role stability."""
    # RBs need either rushing role OR passing role
    min_snap_share = config.get("rb_min_snap_share", 0.40)
    snaps_stable = features.snap_share >= min_snap_share
    if not snaps_stable:
        flags.append(f"rb_snap_share_low:{features.snap_share:.2f}<{min_snap_share}")

    # Rushing role
    min_rush_share = config.get("rb_min_rush_share", 0.25)
    rush_role = features.rush_share >= min_rush_share
    if not rush_role:
        flags.append(f"rb_rush_share_low:{features.rush_share:.2f}<{min_rush_share}")

    # Passing role (alternative)
    min_target_share = config.get("rb_min_target_share", 0.10)
    passing_role = features.target_share_proxy >= min_target_share
    if not passing_role:
        flags.append(f"rb_target_share_low:{features.target_share_proxy:.2f}<{min_target_share}")

    # Must have snap share AND (rush role OR passing role)
    has_clear_role = rush_role or passing_role

    # Role score
    role_score = 0.0
    if snaps_stable:
        role_score += 0.4
    if rush_role:
        role_score += 0.4
    if passing_role:
        role_score += 0.2

    min_role_score = config.get("min_role_score", 0.60)
    passed = snaps_stable and has_clear_role and role_score >= min_role_score

    if not passed:
        flags.append(f"rb_role_score_low:{role_score:.2f}<{min_role_score}")

    return RoleStabilityResult(
        passed=passed,
        role_score=role_score,
        position="RB",
        snaps_stable=snaps_stable,
        flags=flags,
    )


def _check_qb_stability(
    features: FeatureSet,
    market: Market,
    config: dict,
    flags: List[str],
) -> RoleStabilityResult:
    """Check QB role stability (starter check)."""
    # QBs must be starters (snap share > 95%)
    min_snap_share = config.get("qb_min_snap_share", 0.95)
    snaps_stable = features.snap_share >= min_snap_share

    if not snaps_stable:
        flags.append(f"qb_not_starter:{features.snap_share:.2f}<{min_snap_share}")

    role_score = 1.0 if snaps_stable else 0.0

    return RoleStabilityResult(
        passed=snaps_stable,
        role_score=role_score,
        position="QB",
        snaps_stable=snaps_stable,
        flags=flags,
    )
