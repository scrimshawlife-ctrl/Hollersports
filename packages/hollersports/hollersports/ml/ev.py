"""Expected-value layer — advisory only (no stakes placed)."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.ml.features import american_to_decimal

# Default: require 3% edge vs fair (EV > 0.03).
DEFAULT_EV_THRESHOLD = 0.03


def compute_ev(model_probability: float, american_price: float | int | None) -> float | None:
    """EV = p * decimal_odds - 1. None if price unusable."""
    try:
        p = float(model_probability)
    except (TypeError, ValueError):
        return None
    if not (0.0 < p < 1.0):
        return None
    dec = american_to_decimal(american_price)
    if dec is None or dec <= 1.0:
        return None
    return p * dec - 1.0


def annotate_ev(
    *,
    model_probability: float,
    american_price: float | int | None,
    market_implied: float | None = None,
    ev_threshold: float = DEFAULT_EV_THRESHOLD,
) -> dict[str, Any]:
    """Return EV features + advisory flags. Never sets execution authority."""
    ev = compute_ev(model_probability, american_price)
    edge = None
    if market_implied is not None:
        try:
            edge = float(model_probability) - float(market_implied)
        except (TypeError, ValueError):
            edge = None
    meets = ev is not None and ev >= float(ev_threshold)
    return {
        "expected_value": ev,
        "ev_threshold": float(ev_threshold),
        "ev_meets_threshold": meets,
        "model_minus_implied": edge,
        "status": "ADVISORY_ONLY",
        "capital_authority": False,
        "execution_authority": False,
    }
