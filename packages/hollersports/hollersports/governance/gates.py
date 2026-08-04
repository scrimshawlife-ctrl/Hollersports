"""Calibration and other governance gates."""

from __future__ import annotations

from typing import Any, Mapping


def calibration_allows_model_edge(gate: dict | Mapping[str, Any] | None) -> bool:
    """True only when calibration explicitly allows forecast weighting and is RELIABLE.

    Missing/empty gate → False (model edge stays offline).
    """
    if not gate:
        return False
    return bool(gate.get("allow_forecast_weighting")) and gate.get(
        "reliability_status"
    ) == "RELIABLE"
