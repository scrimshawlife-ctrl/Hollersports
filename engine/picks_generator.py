# FILE: HollerSports/engine/picks_generator.py
# ABX-Core compliant pick selection.
# Purpose: select optimal picks from simulated markets using proper state isolation.

from __future__ import annotations

from typing import Any, Dict, List
import logging

from .reset_state import RunState, make_market_key

logger = logging.getLogger(__name__)


def select_optimal_picks(
    state: RunState,
    *,
    strategy: str = "edge",
    min_edge: float = 0.05,
    max_picks: int = 10,
) -> List[Dict[str, Any]]:
    """
    Select optimal picks from simulated markets.

    Integration with state management:
    - Reads from state.simulations (slate-scoped)
    - Reads from state.market.lines (snapshot-protected)
    - Applies state.calibration.adjustments (if enabled)
    - Returns picks that will be stored in state.picks

    Args:
        state: Current RunState (slate-scoped)
        strategy: Selection strategy
            - "edge": maximize expected value
            - "kelly": Kelly criterion sizing
            - "variance_adjusted": risk-adjusted edge
        min_edge: Minimum edge threshold (0.05 = 5%)
        max_picks: Maximum number of picks to return

    Returns:
        List of pick dictionaries with metadata
    """
    if not state.simulations:
        logger.warning("No simulations available - cannot generate picks")
        return []

    picks = []

    logger.info(f"Evaluating {len(state.simulations)} simulated markets")

    for market_key, sim_result in state.simulations.items():
        # Extract simulation results
        prob_over = sim_result.get("prob_over", 0.0)
        prob_under = sim_result.get("prob_under", 0.0)
        mean_simulated = sim_result.get("mean", 0.0)
        std_simulated = sim_result.get("std", 0.0)
        metadata = sim_result.get("metadata", {})

        # Get market line from state
        line_data = state.market.lines.get(market_key, {})
        line_value = line_data.get("line", 0.0)

        # Apply calibration adjustments if enabled
        player_id = metadata.get("player_id")
        calibration_delta = 0.0

        if state.calibration.enabled and player_id:
            player_key = f"{state.slate.sport}:player:{player_id}"
            if player_key in state.calibration.adjustments:
                adj = state.calibration.adjustments[player_key]
                market_type = metadata.get("market", "")
                calibration_delta = adj.get(f"{market_type}_delta", 0.0)

        # Adjust probabilities based on calibration
        adjusted_prob_over = min(max(prob_over + calibration_delta, 0.0), 1.0)
        adjusted_prob_under = 1.0 - adjusted_prob_over

        # Calculate edges for both sides
        # Assuming implied odds of -110 (1.909 decimal, ~52.4% breakeven)
        breakeven_prob = 0.524

        edge_over = adjusted_prob_over - breakeven_prob
        edge_under = adjusted_prob_under - breakeven_prob

        # Select best side
        if edge_over > edge_under and edge_over >= min_edge:
            side = "OVER"
            edge = edge_over
            win_prob = adjusted_prob_over
        elif edge_under >= min_edge:
            side = "UNDER"
            edge = edge_under
            win_prob = adjusted_prob_under
        else:
            continue  # No sufficient edge

        # Calculate expected value and variance metrics
        expected_value = (win_prob * 0.909) - ((1.0 - win_prob) * 1.0)  # -110 odds
        variance = win_prob * (1.0 - win_prob)
        sharpe = edge / (variance ** 0.5) if variance > 0 else 0.0

        # Strategy-specific scoring
        if strategy == "edge":
            score = edge
        elif strategy == "kelly":
            # Simplified Kelly fraction
            kelly_fraction = edge / 0.909
            score = kelly_fraction * win_prob
        elif strategy == "variance_adjusted":
            score = sharpe
        else:
            logger.warning(f"Unknown strategy '{strategy}', defaulting to edge")
            score = edge

        pick = {
            "market_key": market_key,
            "sport": state.slate.sport,
            "game_id": metadata.get("game_id"),
            "player_id": player_id,
            "player_name": metadata.get("player_name"),
            "market": metadata.get("market"),
            "line": line_value,
            "side": side,
            "win_probability": win_prob,
            "edge": edge,
            "expected_value": expected_value,
            "sharpe_ratio": sharpe,
            "score": score,
            "simulated_mean": mean_simulated,
            "simulated_std": std_simulated,
            "calibration_delta": calibration_delta,
        }

        picks.append(pick)

    # Sort by score and take top N
    picks.sort(key=lambda p: p["score"], reverse=True)
    picks = picks[:max_picks]

    logger.info(
        f"Selected {len(picks)} picks using {strategy} strategy | "
        f"Min edge: {min_edge:.2%} | "
        f"Avg edge: {sum(p['edge'] for p in picks) / len(picks):.2%}" if picks else "No picks selected"
    )

    return picks


def build_pick_combinations(
    picks: List[Dict[str, Any]],
    *,
    max_combo_size: int = 6,
    min_combo_size: int = 2,
) -> List[Dict[str, Any]]:
    """
    Build parlay combinations from individual picks.

    Args:
        picks: List of individual picks
        max_combo_size: Maximum legs per parlay
        min_combo_size: Minimum legs per parlay

    Returns:
        List of parlay combinations with aggregate metrics
    """
    from itertools import combinations

    combos = []

    for size in range(min_combo_size, min(max_combo_size + 1, len(picks) + 1)):
        for combo in combinations(picks, size):
            # Calculate aggregate probability (assuming independence)
            aggregate_prob = 1.0
            for pick in combo:
                aggregate_prob *= pick["win_probability"]

            # Calculate parlay odds and expected value
            # Standard parlay odds: (1.909^n) - 1
            parlay_multiplier = (1.909 ** size) - 1
            expected_value = (aggregate_prob * parlay_multiplier) - (1.0 - aggregate_prob)

            combo_dict = {
                "legs": list(combo),
                "size": size,
                "aggregate_probability": aggregate_prob,
                "parlay_multiplier": parlay_multiplier,
                "expected_value": expected_value,
                "total_edge": sum(pick["edge"] for pick in combo),
            }

            combos.append(combo_dict)

    # Sort by expected value
    combos.sort(key=lambda c: c["expected_value"], reverse=True)

    logger.info(f"Built {len(combos)} parlay combinations from {len(picks)} picks")

    return combos


def apply_bankroll_management(
    picks: List[Dict[str, Any]],
    *,
    bankroll: float,
    method: str = "flat",
    risk_percentage: float = 0.02,
) -> List[Dict[str, Any]]:
    """
    Apply bankroll management to picks.

    Args:
        picks: List of picks with edge/probability
        bankroll: Total bankroll
        method: Sizing method ("flat", "kelly", "fractional_kelly")
        risk_percentage: Risk per pick (for flat betting)

    Returns:
        Picks with added 'stake' field
    """
    sized_picks = []

    for pick in picks:
        if method == "flat":
            stake = bankroll * risk_percentage
        elif method == "kelly":
            # Full Kelly: f = (p * b - q) / b, where b = odds, p = prob, q = 1-p
            b = 0.909  # -110 odds
            p = pick["win_probability"]
            q = 1.0 - p
            kelly_fraction = (p * b - q) / b
            stake = bankroll * max(0.0, min(kelly_fraction, 0.25))  # Cap at 25%
        elif method == "fractional_kelly":
            # Quarter Kelly for safety
            b = 0.909
            p = pick["win_probability"]
            q = 1.0 - p
            kelly_fraction = (p * b - q) / b
            stake = bankroll * max(0.0, min(kelly_fraction * 0.25, 0.05))  # Cap at 5%
        else:
            logger.warning(f"Unknown sizing method '{method}', defaulting to flat")
            stake = bankroll * risk_percentage

        sized_pick = pick.copy()
        sized_pick["stake"] = stake
        sized_pick["potential_win"] = stake * 0.909  # -110 odds
        sized_pick["potential_loss"] = stake

        sized_picks.append(sized_pick)

    logger.info(
        f"Applied {method} bankroll management | "
        f"Total stake: ${sum(p['stake'] for p in sized_picks):.2f} | "
        f"Bankroll: ${bankroll:.2f}"
    )

    return sized_picks
