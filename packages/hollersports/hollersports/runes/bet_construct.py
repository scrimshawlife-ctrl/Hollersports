"""Build paper bet constructs from strategy candidates (no live execution)."""

from __future__ import annotations

from typing import Any, Mapping


def construct_bet(
    candidate: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    stake: float,
) -> dict[str, Any]:
    """Construct a paper bet dict from a candidate and execution context.

    Pure mapping of fields; does not place orders or touch capital rails.
    """
    strategy_id = str(candidate.get("strategy_id") or "")
    event_id = str(candidate.get("event_id") or "")
    market_id = str(candidate.get("market_id") or "")
    selection = str(candidate.get("selection") or "")
    candidate_id = str(
        candidate.get("candidate_id")
        or f"{strategy_id}:{event_id}:{market_id}:{selection}"
    )
    packet_refs = candidate.get("packet_refs") or {}
    if not isinstance(packet_refs, Mapping):
        packet_refs = {}

    price = context.get("price", candidate.get("price", 0.0))
    point = context.get("point", candidate.get("point"))
    sportsbook = str(context.get("sportsbook") or candidate.get("sportsbook") or "")
    expected_value = float(
        context.get("expected_value", candidate.get("expected_value", 0.0)) or 0.0
    )

    return {
        "candidate_id": candidate_id,
        "event_id": event_id,
        "market_id": market_id,
        "selection": selection,
        "price": float(price) if price is not None else 0.0,
        "point": float(point) if point is not None else None,
        "sportsbook": sportsbook,
        "stake": float(stake),
        "expected_value": expected_value,
        "packet_refs": dict(packet_refs),
        "strategy_id": strategy_id,
    }
