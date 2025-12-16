"""
Opponent pressure adjustments for NFL.

Bounded secondary layer for matchup-specific modifiers.
"""

from typing import Optional
from hollersports.nfl.types import NFLGameRow, Market


def compute_opponent_modifier(
    market: Market,
    target_game: NFLGameRow,
    config: dict,
) -> float:
    """
    Compute opponent-based modifier.

    Conservative bounded adjustments based on defensive matchup.

    Args:
        market: Target market
        target_game: Game context with opponent defense proxies
        config: Configuration dict

    Returns:
        Multiplicative modifier (bounded to [0.90, 1.10])

    Model:
        - Use opponent_pass_def_proxy / opponent_rush_def_proxy
        - Map to [-1, +1] range
        - Apply conservative scaling (±10% max)
    """
    max_adjustment = config.get("opponent_max_adjustment", 0.10)

    # Determine which defensive proxy to use
    if market in (Market.RECEPTIONS, Market.REC_YDS, Market.TARGETS, Market.PASS_ATT, Market.PASS_YDS):
        # Passing markets: use pass defense proxy
        def_proxy = target_game.opponent_pass_def_proxy
    elif market in (Market.RUSH_ATT, Market.RUSH_YDS):
        # Rushing markets: use rush defense proxy
        def_proxy = target_game.opponent_rush_def_proxy
    else:
        # Event markets (TDs): no opponent adjustment
        return 1.0

    if def_proxy is None:
        return 1.0  # No data: neutral modifier

    # Map defense proxy to modifier
    # Assume def_proxy is normalized to ~[-2, +2]
    # Positive def_proxy = tough defense → negative modifier
    # Negative def_proxy = weak defense → positive modifier

    # Clamp def_proxy to [-2, 2]
    def_proxy_clamped = max(-2.0, min(2.0, def_proxy))

    # Map to [-max_adjustment, +max_adjustment]
    # Invert sign: tough defense (positive proxy) should lower projection
    adjustment = -def_proxy_clamped * (max_adjustment / 2.0)

    # Clamp to bounds
    modifier = 1.0 + adjustment
    modifier = max(0.90, min(1.10, modifier))

    return modifier


def compute_home_field_modifier(
    target_game: NFLGameRow,
    config: dict,
) -> float:
    """
    Compute home field advantage modifier.

    Small boost for home teams.

    Args:
        target_game: Game context
        config: Configuration dict

    Returns:
        Multiplicative modifier (typically 1.00 - 1.03)
    """
    home_boost = config.get("home_field_boost", 0.02)

    if target_game.is_home == 1:
        return 1.0 + home_boost
    else:
        return 1.0


def apply_opponent_adjustments(
    median: float,
    market: Market,
    target_game: NFLGameRow,
    config: dict,
) -> float:
    """
    Apply all opponent-based adjustments.

    Args:
        median: Base median projection
        market: Target market
        target_game: Game context
        config: Configuration dict

    Returns:
        Adjusted median
    """
    # Opponent defense modifier
    opponent_mod = compute_opponent_modifier(market, target_game, config)

    # Home field modifier
    home_mod = compute_home_field_modifier(target_game, config)

    # Apply both modifiers
    adjusted = median * opponent_mod * home_mod

    return adjusted
