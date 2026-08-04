"""Offline fixture day adapter: merge ESPN-like events with odds markets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _as_event_list(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, dict):
        events = raw.get("events")
        if isinstance(events, list):
            return [e for e in events if isinstance(e, dict)]
    return []


def _as_market_list(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [m for m in raw if isinstance(m, dict)]
    if isinstance(raw, dict):
        markets = raw.get("markets")
        if isinstance(markets, list):
            return [m for m in markets if isinstance(m, dict)]
    return []


def _markets_for_event(
    markets: list[dict[str, Any]], event_id: str
) -> list[dict[str, Any]]:
    matched = [m for m in markets if m.get("event_id") == event_id]
    if matched:
        return matched
    # If records omit event_id and only one event is present, attach all.
    untagged = [m for m in markets if "event_id" not in m]
    return untagged if untagged else []


def _pick_primary_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not events:
        return None
    for event in events:
        if str(event.get("league", "")).upper() == "NBA":
            return event
    return events[0]


def load_fixture_day(path: Path | str) -> dict[str, Any]:
    """Load a fixture day directory and build an ingest payload for strategies.

    Expected files under ``path``:
    - meta.json
    - espn_events.json
    - odds_records.json

    Returns dict with ``meta``, ``events`` (markets merged), and ``ingest_payload``
    suitable for ``run_market_ingestion``.
    """
    day_path = Path(path)
    meta = _read_json(day_path / "meta.json")
    if not isinstance(meta, dict):
        meta = {}

    events = _as_event_list(_read_json(day_path / "espn_events.json"))
    markets = _as_market_list(_read_json(day_path / "odds_records.json"))

    merged_events: list[dict[str, Any]] = []
    for event in events:
        eid = str(event.get("event_id", ""))
        event_markets = _markets_for_event(markets, eid)
        merged = dict(event)
        merged["markets"] = event_markets
        merged_events.append(merged)

    primary = _pick_primary_event(merged_events)
    day_name = day_path.name

    if primary is None:
        payload: dict[str, Any] = {
            "event_id": "UNKNOWN",
            "sport": "UNKNOWN",
            "league": "UNKNOWN",
            "teams": [],
            "markets": [],
        }
    else:
        payload = {
            "event_id": primary.get("event_id", "UNKNOWN"),
            "sport": primary.get("sport", "UNKNOWN"),
            "league": primary.get("league", "UNKNOWN"),
            "teams": list(primary.get("teams") or []),
            "markets": list(primary.get("markets") or []),
        }
        for key in ("home_team", "away_team", "start_time", "status"):
            if key in primary:
                payload[key] = primary[key]

    ingest_payload: dict[str, Any] = {
        "run_id": meta.get("run_id", f"FIX-{day_name.upper()}"),
        "source_id": "FIXTURE",
        "source_type": "MANUAL",
        "fetched_at": meta.get("fetched_at", ""),
        "current_time": meta.get("current_time", ""),
        "required_fields": ["event_id", "markets"],
        "source_refs": {"source": "FIXTURE", "day": day_name},
        "payload": payload,
    }

    return {
        "meta": meta,
        "events": merged_events,
        "markets": markets,
        "ingest_payload": ingest_payload,
    }
