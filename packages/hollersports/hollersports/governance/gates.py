"""Calibration and other governance gates."""

from __future__ import annotations

from typing import Any, Mapping


def calibration_allows_model_edge(gate: dict | Mapping[str, Any] | None) -> bool:
    """True only when calibration explicitly allows forecast weighting and is RELIABLE.

    Missing/empty gate → False (model edge stays offline).

    Accepts:
      - gate dict with ``allow_forecast_weighting`` + ``reliability_status``
      - full CalibrationPacket.v1 (same fields + optional ``model_edge_allowed``)
    """
    if not gate:
        return False
    # Prefer explicit precomputed flag when present (from evaluate_calibration).
    if "model_edge_allowed" in gate:
        return bool(gate.get("model_edge_allowed"))
    status = str(gate.get("reliability_status") or gate.get("status") or "")
    return bool(gate.get("allow_forecast_weighting")) and status == "RELIABLE"
