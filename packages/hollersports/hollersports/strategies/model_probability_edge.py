"""MODEL_PROBABILITY_EDGE — gated model/forecast edge (offline in v1)."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.strategies.base import BaseStrategy


class ModelProbabilityEdge(BaseStrategy):
    """Registered when calibration allows; still returns [] until model is wired."""

    strategy_id = "MODEL_PROBABILITY_EDGE"
    strategy_family = "MODEL"

    def generate(self, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
        # v1: model not wired — never invent candidates.
        return []
