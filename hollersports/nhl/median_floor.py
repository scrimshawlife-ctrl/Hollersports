"""
Median-Floor Engine for NHL SOG projections.

Core projection logic using weighted recency + season median + conservative floor.
"""

from typing import Tuple, List
import numpy as np

from hollersports.nhl.types import FeatureSet


# Configuration defaults
DEFAULT_CONFIG = {
    "median_last5_weight": 0.6,
    "median_season_weight": 0.4,
    "floor_percentile": 25,
    "volatility_std_threshold": 2.0,
    "volatility_penalty": 0.15,  # Reduce projection by 15% if volatile
    "min_games_for_floor": 5,
}


def compute_median_floor(
    features: FeatureSet,
    config: dict = None,
) -> Tuple[float, float, float]:
    """
    Compute median projection and conservative floor.

    Methodology:
    - median = 0.6 * last5_weighted + 0.4 * season_median
    - floor = min(median, p25(last_N))
    - Apply volatility penalty if boom/bust pattern detected

    Args:
        features: FeatureSet with historical data
        config: Optional configuration overrides

    Returns:
        Tuple of (median, floor, sigma_proxy)
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Extract config
    last5_weight = config.get("median_last5_weight", 0.6)
    season_weight = config.get("median_season_weight", 0.4)
    floor_percentile = config.get("floor_percentile", 25)
    volatility_threshold = config.get("volatility_std_threshold", 2.0)
    volatility_penalty = config.get("volatility_penalty", 0.15)
    min_games = config.get("min_games_for_floor", 5)

    # Base median calculation
    median = (last5_weight * features.last5_sog_weighted +
              season_weight * features.season_sog_median)

    # Floor calculation
    floor = median  # Default: same as median

    if len(features.last10_sog_list) >= min_games:
        floor_estimate = float(np.percentile(features.last10_sog_list, floor_percentile))
        floor = min(median, floor_estimate)

    # Sigma proxy (standard deviation estimate)
    if len(features.last10_sog_list) >= 3:
        sigma_proxy = float(np.std(features.last10_sog_list))
    else:
        # Fallback: assume ~30% coefficient of variation
        sigma_proxy = median * 0.3

    # Volatility check: boom/bust pattern
    is_volatile = False
    if len(features.last10_sog_list) >= 5:
        std_last10 = float(np.std(features.last10_sog_list))
        if std_last10 > volatility_threshold:
            is_volatile = True

            # Downgrade if boom/bust and floor is concerning
            if floor < median * 0.7:  # Floor significantly below median
                median = median * (1 - volatility_penalty)
                floor = floor * (1 - volatility_penalty)

    return median, floor, sigma_proxy


def assess_projection_quality(
    median: float,
    floor: float,
    line: float,
    side: str,
) -> Tuple[float, List[str]]:
    """
    Assess quality of projection relative to line.

    Args:
        median: Median projection
        floor: Conservative floor
        line: Prop line
        side: "HIGHER" or "LOWER"

    Returns:
        Tuple of (quality_score 0-1, reasons list)
    """
    reasons = []
    quality = 0.5  # Base

    if side == "HIGHER":
        # Over bet: want median > line and floor close to line
        if median > line:
            gap = median - line
            reasons.append(f"Median {median:.1f} above line {line:.1f} (+{gap:.1f})")
            quality += min(0.3, gap / 5.0)  # Up to +0.3 for large gap

        if floor >= line:
            reasons.append(f"Floor {floor:.1f} at/above line {line:.1f} (safe)")
            quality += 0.2
        elif floor >= line * 0.9:
            reasons.append(f"Floor {floor:.1f} near line {line:.1f} (acceptable)")
            quality += 0.1
        else:
            reasons.append(f"Floor {floor:.1f} below line {line:.1f} (risk)")
            quality -= 0.2

    else:  # LOWER
        # Under bet: want median < line and floor well below
        if median < line:
            gap = line - median
            reasons.append(f"Median {median:.1f} below line {line:.1f} (-{gap:.1f})")
            quality += min(0.3, gap / 5.0)

        if floor < line * 0.8:
            reasons.append(f"Floor {floor:.1f} safely under line {line:.1f}")
            quality += 0.2
        elif floor < line:
            reasons.append(f"Floor {floor:.1f} below line {line:.1f} (acceptable)")
            quality += 0.1
        else:
            reasons.append(f"Floor {floor:.1f} at/above line {line:.1f} (risk)")
            quality -= 0.2

    # Clamp quality
    quality = max(0.0, min(1.0, quality))

    return quality, reasons
