"""
Script-Conditioned Median Floor Engine for NFL.

Computes median and floor projections conditioned on game script probabilities.
"""

from typing import Dict, Optional
import numpy as np

from hollersports.nfl.types import FeatureSet, Market, ScriptState, NFLGameRow
from hollersports.nfl.script_tree import compute_script_weighted_median


def compute_median_floor(
    features: FeatureSet,
    market: Market,
    script_priors: Dict[ScriptState, float],
    target_game: NFLGameRow,
    config: dict,
) -> tuple[float, float, float, Dict[str, float]]:
    """
    Compute script-conditioned median, floor, and sigma.

    Args:
        features: Player feature set
        market: Target market
        script_priors: Script state probabilities
        target_game: Target game context
        config: Configuration dict

    Returns:
        (median, floor, sigma, script_mus) tuple
        - median: Script-weighted median projection
        - floor: Conservative floor estimate
        - sigma: Standard deviation proxy
        - script_mus: Dict[state_name, mu] for each script state
    """
    # Compute neutral median (baseline without script conditioning)
    neutral_median = _compute_neutral_median(features, market)

    if neutral_median == 0:
        return 0.0, 0.0, 0.0, {}

    # Compute script-specific projections
    script_mus = {}
    for state, prob in script_priors.items():
        from hollersports.nfl.script_tree import get_script_modifier
        modifier = get_script_modifier(state, market.value, features.position)
        script_mus[state.value] = neutral_median * modifier

    # Compute script-weighted median
    median = compute_script_weighted_median(
        neutral_median,
        script_priors,
        market.value,
        features.position,
    )

    # Compute floor (25th percentile from historical distribution)
    floor = _compute_floor(features, market, median)

    # Compute sigma (volatility proxy)
    sigma = _compute_sigma(features, market, median)

    return median, floor, sigma, script_mus


def _compute_neutral_median(features: FeatureSet, market: Market) -> float:
    """
    Compute neutral median (no script conditioning).

    Weighted blend of recent performance and season median.
    """
    if market == Market.RECEPTIONS:
        last5_weighted = _weighted_avg(features.last5_receptions, decay=0.85)
        season_median = features.season_receptions_median
        return 0.6 * last5_weighted + 0.4 * season_median

    elif market == Market.REC_YDS:
        # Use receptions median * yards per reception proxy
        last5_receptions = _weighted_avg(features.last5_receptions, decay=0.85)
        # Assume ~12 yards per reception
        ypr = 12.0
        return last5_receptions * ypr

    elif market == Market.TARGETS:
        last5_weighted = _weighted_avg(features.last5_targets, decay=0.85)
        season_median = features.season_targets_median
        return 0.6 * last5_weighted + 0.4 * season_median

    elif market == Market.RUSH_ATT:
        last5_weighted = _weighted_avg(features.last5_rush_att, decay=0.85)
        # No season median for rush attempts in FeatureSet
        return last5_weighted

    elif market == Market.RUSH_YDS:
        # Rush attempts * yards per carry proxy
        last5_attempts = _weighted_avg(features.last5_rush_att, decay=0.85)
        # Assume ~4.3 yards per carry
        ypc = 4.3
        return last5_attempts * ypc

    elif market == Market.PASS_ATT:
        # For QBs only - would need pass_attempts in features
        # Return 0 for now (needs enhancement)
        return 0.0

    elif market == Market.PASS_YDS:
        # For QBs only - would need pass_yards in features
        # Return 0 for now (needs enhancement)
        return 0.0

    else:
        # Event markets (TDs) - return 0 (forbidden in ultra-safe)
        return 0.0


def _compute_floor(features: FeatureSet, market: Market, median: float) -> float:
    """
    Compute conservative floor.

    Floor = min(median, p25_historical)
    """
    if market == Market.RECEPTIONS:
        historical = features.last5_receptions
    elif market == Market.TARGETS:
        historical = features.last5_targets
    elif market == Market.RUSH_ATT:
        historical = features.last5_rush_att
    elif market == Market.REC_YDS:
        # Use receptions as proxy
        historical = features.last5_receptions
    elif market == Market.RUSH_YDS:
        # Use rush attempts as proxy
        historical = features.last5_rush_att
    else:
        return median * 0.75  # Default floor

    if len(historical) < 3:
        return median * 0.75

    p25 = float(np.percentile(historical, 25))

    # For yardage markets, scale p25 by median ratio
    if market in (Market.REC_YDS, Market.RUSH_YDS):
        if market == Market.REC_YDS:
            base_median = _weighted_avg(features.last5_receptions, decay=0.85)
        else:
            base_median = _weighted_avg(features.last5_rush_att, decay=0.85)

        if base_median > 0:
            p25 = p25 * (median / base_median)

    return min(median, p25)


def _compute_sigma(features: FeatureSet, market: Market, median: float) -> float:
    """
    Compute standard deviation proxy.

    sigma = sqrt(variance)
    """
    if market == Market.RECEPTIONS:
        historical = features.last5_receptions
    elif market == Market.TARGETS:
        historical = features.last5_targets
    elif market == Market.RUSH_ATT:
        historical = features.last5_rush_att
    else:
        # For yardage, use coefficient of variation from count data
        if market == Market.REC_YDS:
            historical = features.last5_receptions
        elif market == Market.RUSH_YDS:
            historical = features.last5_rush_att
        else:
            return median * 0.4  # Default sigma

    if len(historical) < 3:
        return median * 0.4

    std = float(np.std(historical))

    # For yardage markets, scale std by median ratio
    if market in (Market.REC_YDS, Market.RUSH_YDS):
        if market == Market.REC_YDS:
            base_median = _weighted_avg(features.last5_receptions, decay=0.85)
        else:
            base_median = _weighted_avg(features.last5_rush_att, decay=0.85)

        if base_median > 0:
            cv = std / max(base_median, 1.0)
            std = cv * median

    # Ensure sigma >= 1.0 for count data stability
    if market in (Market.RECEPTIONS, Market.TARGETS, Market.RUSH_ATT):
        std = max(std, 1.0)

    return std


def _weighted_avg(values: list, decay: float = 0.85) -> float:
    """
    Compute exponentially weighted average.

    Most recent games have higher weight.

    Args:
        values: List of values (oldest to newest)
        decay: Decay factor (0 < decay < 1)

    Returns:
        Weighted average
    """
    if not values:
        return 0.0

    weights = [decay ** (len(values) - 1 - i) for i in range(len(values))]
    weighted_sum = sum(w * v for w, v in zip(weights, values))
    weight_sum = sum(weights)

    return weighted_sum / weight_sum if weight_sum > 0 else 0.0
