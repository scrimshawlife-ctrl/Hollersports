"""
Role Stability Filter for NHL SOG projections.

Hard gates and soft boosts based on TOI and PP usage stability.
"""

from typing import List

from hollersports.nhl.types import FeatureSet, RoleStabilityResult


# Configuration defaults
DEFAULT_CONFIG = {
    "min_toi_season": 14.0,  # Minimum season TOI median (minutes)
    "toi_stability_threshold": 0.15,  # +/- 15% tolerance
    "pp_stability_threshold": 0.20,  # +/- 20% tolerance for PP share
    "min_games_for_stability": 5,
}


def check_role_stability(
    features: FeatureSet,
    config: dict = None,
) -> RoleStabilityResult:
    """
    Check role stability for a player.

    Hard gates:
    - TOI season median >= min_toi_season
    - TOI last5 median within +/- threshold of season median

    Soft boosts:
    - PP share stable (if available)

    Args:
        features: FeatureSet with TOI and PP data
        config: Optional configuration overrides

    Returns:
        RoleStabilityResult with pass/fail and scores
    """
    if config is None:
        config = DEFAULT_CONFIG

    min_toi = config.get("min_toi_season", 14.0)
    toi_threshold = config.get("toi_stability_threshold", 0.15)
    pp_threshold = config.get("pp_stability_threshold", 0.20)

    flags = []
    toi_stable = False
    pp_stable = False
    role_score = 0.0

    # Hard gate 1: Minimum TOI
    if features.toi_season_median < min_toi:
        flags.append(f"Low TOI: {features.toi_season_median:.1f} < {min_toi:.1f}")
        return RoleStabilityResult(
            passed=False,
            role_score=0.0,
            toi_stable=False,
            pp_stable=False,
            flags=flags,
        )

    # Hard gate 2: TOI stability
    if features.toi_last5_median > 0 and features.toi_season_median > 0:
        toi_ratio = features.toi_last5_median / features.toi_season_median

        if (1 - toi_threshold) <= toi_ratio <= (1 + toi_threshold):
            toi_stable = True
            role_score += 0.6  # Major component
        else:
            flags.append(
                f"TOI unstable: last5={features.toi_last5_median:.1f} "
                f"vs season={features.toi_season_median:.1f} "
                f"(ratio={toi_ratio:.2f})"
            )
            return RoleStabilityResult(
                passed=False,
                role_score=0.0,
                toi_stable=False,
                pp_stable=False,
                flags=flags,
            )

    # Soft boost: PP stability (if available)
    if features.pp_share is not None and features.pp_share_last5 is not None:
        if features.pp_share > 0:
            pp_ratio = features.pp_share_last5 / features.pp_share

            if (1 - pp_threshold) <= pp_ratio <= (1 + pp_threshold):
                pp_stable = True
                role_score += 0.4  # Bonus component
            else:
                flags.append(
                    f"PP usage changed: last5={features.pp_share_last5:.2%} "
                    f"vs season={features.pp_share:.2%}"
                )
                role_score += 0.2  # Partial credit
        else:
            # No PP time - still valid but no bonus
            role_score += 0.2
    else:
        # PP data not available - no penalty
        role_score += 0.3

    # Clamp role score
    role_score = min(1.0, role_score)

    return RoleStabilityResult(
        passed=True,
        role_score=role_score,
        toi_stable=toi_stable,
        pp_stable=pp_stable,
        flags=flags,
    )
