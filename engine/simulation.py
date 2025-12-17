# FILE: HollerSports/engine/simulation.py
# ABX-Core compliant Monte Carlo simulation engine.
# Purpose: run deterministic simulations using slate-scoped state.

from __future__ import annotations

from typing import Any, Dict, Optional
import logging
import random
import math

from .reset_state import RunState, make_market_key

logger = logging.getLogger(__name__)


def run_monte_carlo_simulations(
    state: RunState,
    *,
    iterations: int = 10000,
    sim_engine: Optional[Any] = None,
    seed: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Run Monte Carlo simulations for all markets in the slate.

    Integration with state management:
    - Reads from state.market.lines (snapshot-protected)
    - Reads from state.game_context (slate-scoped)
    - Applies state.calibration.adjustments (if enabled)
    - Returns simulation results to be stored in state.simulations

    Args:
        state: Current RunState (slate-scoped)
        iterations: Number of Monte Carlo iterations per market
        sim_engine: Optional external simulation engine
        seed: Random seed for determinism (provenance only)

    Returns:
        Dict keyed by market_key containing simulation results
    """
    if seed is not None:
        random.seed(seed)
        state.provenance["simulation_seed"] = seed

    simulations = {}

    logger.info(f"Running Monte Carlo simulations: {iterations} iterations")

    # Iterate through all markets in the snapshot
    for market_key, line_data in state.market.lines.items():
        try:
            sim_result = _simulate_market(
                state=state,
                market_key=market_key,
                line_data=line_data,
                iterations=iterations,
                sim_engine=sim_engine,
            )
            simulations[market_key] = sim_result
        except Exception as e:
            logger.error(f"Simulation failed for {market_key}: {e}")
            continue

    logger.info(f"Simulations complete: {len(simulations)} markets")

    return simulations


def _simulate_market(
    state: RunState,
    market_key: str,
    line_data: Dict[str, Any],
    iterations: int,
    sim_engine: Optional[Any],
) -> Dict[str, Any]:
    """
    Simulate a single market.

    This is where the core statistical modeling happens.
    Integration point: Replace with actual ABX-Core symbolic engine.
    """
    # Extract line metadata
    sport = line_data.get("sport", state.slate.sport)
    game_id = line_data.get("game_id")
    player_id = line_data.get("player_id")
    player_name = line_data.get("player_name", "Unknown")
    market_type = line_data.get("market", "PTS")  # "PTS", "AST", "REB", etc.
    line_value = line_data.get("line", 0.0)

    # Get game context modifiers
    game_context = state.game_context.by_game_id.get(game_id, {})

    # Base player statistics (placeholder - integrate with actual player database)
    # In production, this would query historical stats, recent form, matchup data, etc.
    player_stats = _get_player_base_stats(
        sport=sport,
        player_id=player_id,
        market_type=market_type,
        sim_engine=sim_engine,
    )

    # Apply game context adjustments
    adjusted_mean, adjusted_std = _apply_game_context(
        base_mean=player_stats["mean"],
        base_std=player_stats["std"],
        game_context=game_context,
        market_type=market_type,
    )

    # Apply calibration adjustments if enabled
    if state.calibration.enabled and player_id:
        player_key = f"{sport}:player:{player_id}"
        if player_key in state.calibration.adjustments:
            adj = state.calibration.adjustments[player_key]
            mean_delta = adj.get(f"{market_type}_mean_delta", 0.0)
            std_multiplier = adj.get(f"{market_type}_std_multiplier", 1.0)

            adjusted_mean += mean_delta
            adjusted_std *= std_multiplier

    # Run Monte Carlo simulation
    samples = []
    for _ in range(iterations):
        # Use log-normal for count stats (always positive, right-skewed)
        if market_type in ["PTS", "AST", "REB", "3PM", "BLK", "STL"]:
            sample = _sample_lognormal(adjusted_mean, adjusted_std)
        else:
            # Use normal for continuous stats
            sample = random.gauss(adjusted_mean, adjusted_std)

        samples.append(max(0.0, sample))  # Enforce non-negative

    # Calculate statistics
    samples.sort()
    mean_simulated = sum(samples) / len(samples)
    variance = sum((x - mean_simulated) ** 2 for x in samples) / len(samples)
    std_simulated = math.sqrt(variance)

    # Calculate probabilities
    over_count = sum(1 for s in samples if s > line_value)
    under_count = sum(1 for s in samples if s < line_value)
    push_count = iterations - over_count - under_count

    prob_over = over_count / iterations
    prob_under = under_count / iterations
    prob_push = push_count / iterations

    # Percentile analysis
    percentile_25 = samples[int(iterations * 0.25)]
    percentile_50 = samples[int(iterations * 0.50)]
    percentile_75 = samples[int(iterations * 0.75)]

    result = {
        "market_key": market_key,
        "iterations": iterations,
        "mean": mean_simulated,
        "std": std_simulated,
        "prob_over": prob_over,
        "prob_under": prob_under,
        "prob_push": prob_push,
        "percentiles": {
            "p25": percentile_25,
            "p50": percentile_50,
            "p75": percentile_75,
        },
        "metadata": {
            "sport": sport,
            "game_id": game_id,
            "player_id": player_id,
            "player_name": player_name,
            "market": market_type,
            "line": line_value,
            "base_mean": player_stats["mean"],
            "base_std": player_stats["std"],
            "adjusted_mean": adjusted_mean,
            "adjusted_std": adjusted_std,
        },
    }

    return result


def _get_player_base_stats(
    sport: str,
    player_id: str,
    market_type: str,
    sim_engine: Optional[Any],
) -> Dict[str, float]:
    """
    Get base player statistics.

    Integration point: Connect to actual player database / ABX-Core engine.

    Args:
        sport: Sport code
        player_id: Player identifier
        market_type: Market type (PTS, AST, etc.)
        sim_engine: Optional external engine

    Returns:
        Dict with "mean" and "std" keys
    """
    # Placeholder implementation - replace with actual player database query
    # In production, this would:
    # 1. Query historical performance
    # 2. Apply recency weighting
    # 3. Adjust for matchup difficulty
    # 4. Consider home/away splits
    # 5. Factor in recent trends

    if sim_engine and hasattr(sim_engine, "get_player_stats"):
        return sim_engine.get_player_stats(sport, player_id, market_type)

    # Default placeholder values (for demonstration)
    default_stats = {
        "NBA": {
            "PTS": {"mean": 20.0, "std": 6.0},
            "AST": {"mean": 5.0, "std": 2.5},
            "REB": {"mean": 7.0, "std": 3.0},
            "3PM": {"mean": 2.0, "std": 1.5},
            "PRA": {"mean": 32.0, "std": 8.0},
        },
        "NFL": {
            "PASS_YDS": {"mean": 250.0, "std": 60.0},
            "RUSH_YDS": {"mean": 75.0, "std": 30.0},
            "REC_YDS": {"mean": 60.0, "std": 25.0},
            "TD": {"mean": 1.5, "std": 1.0},
        },
    }

    sport_defaults = default_stats.get(sport, {})
    market_defaults = sport_defaults.get(market_type, {"mean": 10.0, "std": 5.0})

    logger.debug(
        f"Using placeholder stats for {sport}:{player_id}:{market_type} - "
        "Replace with actual player database integration"
    )

    return market_defaults


def _apply_game_context(
    base_mean: float,
    base_std: float,
    game_context: Dict[str, Any],
    market_type: str,
) -> tuple[float, float]:
    """
    Apply game context modifiers to base statistics.

    Args:
        base_mean: Base mean value
        base_std: Base standard deviation
        game_context: Game context dict from state.game_context
        market_type: Market type

    Returns:
        Tuple of (adjusted_mean, adjusted_std)
    """
    adjusted_mean = base_mean
    adjusted_std = base_std

    # Example context adjustments (customize per use case)

    # Venue adjustment
    venue = game_context.get("venue", "neutral")
    if venue == "home":
        adjusted_mean *= 1.02  # 2% boost for home games
    elif venue == "away":
        adjusted_mean *= 0.98  # 2% reduction for away games

    # Pace adjustment (if available)
    pace_factor = game_context.get("pace_factor", 1.0)
    if market_type in ["PTS", "AST", "REB", "PRA"]:
        adjusted_mean *= pace_factor
        adjusted_std *= (pace_factor ** 0.5)  # Variance scales with sqrt of pace

    # Rest adjustment
    days_rest = game_context.get("days_rest", 1)
    if days_rest == 0:  # Back-to-back
        adjusted_mean *= 0.95
        adjusted_std *= 1.1  # Increased variance when fatigued
    elif days_rest >= 3:  # Well-rested
        adjusted_mean *= 1.01
        adjusted_std *= 0.95  # Reduced variance

    # Matchup difficulty
    defensive_rating = game_context.get("opponent_defensive_rating", 100.0)
    if defensive_rating < 95:  # Elite defense
        adjusted_mean *= 0.92
    elif defensive_rating > 110:  # Poor defense
        adjusted_mean *= 1.08

    return adjusted_mean, adjusted_std


def _sample_lognormal(mean: float, std: float) -> float:
    """
    Sample from a log-normal distribution calibrated to target mean/std.

    Args:
        mean: Target mean
        std: Target standard deviation

    Returns:
        Sample value
    """
    # Convert target mean/std to log-normal parameters
    variance = std ** 2
    mu = math.log(mean ** 2 / math.sqrt(variance + mean ** 2))
    sigma = math.sqrt(math.log(1 + variance / (mean ** 2)))

    # Sample from log-normal
    return random.lognormvariate(mu, sigma)
