"""MODEL_PROBABILITY_EDGE — package-native deterministic model edge.

Loaded only when calibration allows (see load_strategies / competition).
Never invents model probabilities: markets must carry ``model_probability``.
Does not wrap legacy engine/ Monte Carlo — that remains out of operator path.
"""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.strategies.base import BaseStrategy, build_candidate

# Minimum model − market implied edge to emit a candidate.
MODEL_EDGE_THRESHOLD = 0.03
# Normalize edge into score ∈ [0, 1] (edge of 0.20 → score 1.0).
_EDGE_SCORE_SCALE = 0.20


def _as_prob(raw: Any) -> float | None:
    """Parse a probability in (0, 1); None if missing/invalid."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if not (0.0 < v < 1.0):
        return None
    return v


class ModelProbabilityEdge(BaseStrategy):
    """Emit SHADOW_ONLY candidates when model edge exceeds threshold."""

    strategy_id = "MODEL_PROBABILITY_EDGE"
    strategy_family = "MODEL"

    def generate(self, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
        run_id, event_id = self._run_event(packet)
        out: list[dict[str, Any]] = []
        for market in self._markets(packet):
            model_p = _as_prob(market.get("model_probability"))
            if model_p is None:
                continue

            implied_raw = market.get("market_implied_probability")
            if implied_raw is None:
                implied_raw = market.get("implied_probability")
            try:
                implied_p = float(implied_raw) if implied_raw is not None else 0.0
            except (TypeError, ValueError):
                continue
            if not (0.0 <= implied_p <= 1.0):
                continue

            edge = model_p - implied_p
            if edge < MODEL_EDGE_THRESHOLD:
                continue

            score = max(0.0, min(1.0, edge / _EDGE_SCORE_SCALE))
            market_id = str(market.get("market_id") or "UNKNOWN")
            selection = str(
                market.get("model_side") or market.get("selection") or "UNKNOWN"
            )
            out.append(
                build_candidate(
                    strategy_id=self.strategy_id,
                    strategy_family=self.strategy_family,
                    run_id=run_id,
                    event_id=str(market.get("event_id") or event_id),
                    market_id=market_id,
                    selection=selection,
                    score=score,
                    confidence=model_p,
                    features={
                        "model_probability": model_p,
                        "market_implied_probability": implied_p,
                        "edge": edge,
                        "threshold": MODEL_EDGE_THRESHOLD,
                    },
                    packet_refs={
                        "run_id": run_id,
                        "market_id": market_id,
                    },
                    provenance={"scoring": "deterministic_model_minus_implied"},
                )
            )
        return out
