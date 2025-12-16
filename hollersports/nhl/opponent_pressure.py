"""
Opponent Pressure Model for NHL SOG projections.

Secondary adjustment based on opponent shot suppression.
Never dominant - bounded to +/- 10% maximum effect.
"""

from typing import List
import numpy as np

from hollersports.nhl.types import FeatureSet, NHLGameRow


# Configuration defaults
DEFAULT_CONFIG = {
    "max_opponent_modifier": 0.10,  # +/- 10% max
    "opponent_effect_weight": 0.5,  # Dampen to 50% of computed effect
}


def compute_opponent_modifier(
    features: FeatureSet,
    all_data: List[NHLGameRow],
    config: dict = None,
) -> float:
    """
    Compute opponent adjustment modifier.

    Methodology:
    - Compute opponent's z-score for SOG allowed to position
    - Convert to modifier: positive z-score (allows more SOG) → positive modifier
    - Apply damping and cap at max_opponent_modifier

    Args:
        features: FeatureSet with opponent context
        all_data: Full dataset for league-wide statistics
        config: Optional configuration overrides

    Returns:
        Opponent modifier in range [-max, +max] (typically +/- 0.10)
    """
    if config is None:
        config = DEFAULT_CONFIG

    max_modifier = config.get("max_opponent_modifier", 0.10)
    effect_weight = config.get("opponent_effect_weight", 0.5)

    # Compute league average and std for this position
    # (already computed in features as opponent_pos_sog_allowed)

    # Get league-wide statistics for this position
    position_games = [g for g in all_data if g.player_id == features.player_id]

    if not position_games:
        return 0.0  # No adjustment if no data

    # Approximate league average by computing mean SOG for all players
    all_sog_values = [g.sog for g in all_data]

    if len(all_sog_values) < 10:
        return 0.0  # Insufficient data

    league_mean = float(np.mean(all_sog_values))
    league_std = float(np.std(all_sog_values))

    if league_std == 0:
        return 0.0

    # Opponent SOG allowed relative to league
    opponent_sog_allowed = features.opponent_pos_sog_allowed

    # Z-score (positive = allows more SOG than average)
    z_score = (opponent_sog_allowed - league_mean) / league_std

    # Convert to modifier
    # z_score of +1 → +10% modifier (capped)
    # z_score of -1 → -10% modifier (capped)
    raw_modifier = z_score * 0.10  # 1 std = 10%

    # Apply damping
    damped_modifier = raw_modifier * effect_weight

    # Cap at max
    modifier = max(-max_modifier, min(max_modifier, damped_modifier))

    return modifier


def apply_opponent_adjustment(
    mu: float,
    opponent_modifier: float,
) -> float:
    """
    Apply opponent modifier to mean projection.

    Args:
        mu: Base mean projection
        opponent_modifier: Computed modifier

    Returns:
        Adjusted mean
    """
    mu_adj = mu * (1 + opponent_modifier)

    # Ensure stays positive and reasonable
    mu_adj = max(0.5, mu_adj)

    return mu_adj
