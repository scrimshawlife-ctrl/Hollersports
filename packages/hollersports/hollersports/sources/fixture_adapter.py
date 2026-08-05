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


def _flatten_markets(
    merged_events: list[dict[str, Any]],
    all_markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """All event markets for strategy competition (multi-league slate).

    Enriches each market with event_id / league / sport from its event when missing.
    Falls back to untagged markets list if events have no market matches.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in merged_events:
        eid = str(event.get("event_id") or "")
        league = str(event.get("league") or "")
        sport = str(event.get("sport") or "")
        for m in event.get("markets") or []:
            if not isinstance(m, dict):
                continue
            row = dict(m)
            mid = str(row.get("market_id") or "")
            if mid and mid in seen:
                continue
            if mid:
                seen.add(mid)
            row.setdefault("event_id", eid)
            if league and not row.get("league"):
                row["league"] = league
            if sport and not row.get("sport"):
                row["sport"] = sport
            out.append(row)
    if out:
        return out
    # No per-event match — use full odds list as-is.
    return [dict(m) for m in all_markets if isinstance(m, dict)]


def load_fixture_day(path: Path | str) -> dict[str, Any]:
    """Load a fixture day directory and build an ingest payload for strategies.

    Expected files under ``path``:
    - meta.json
    - espn_events.json
    - odds_records.json

    Returns dict with ``meta``, ``events`` (markets merged), and ``ingest_payload``
    suitable for ``run_market_ingestion``.

    ``ingest_payload.payload.markets`` includes **all** slate markets (every event),
    not only the primary event — required for multi-sport days and backfill sample.
    Primary event still sets top-level event_id / league identity.
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
    flat_markets = _flatten_markets(merged_events, markets)
    leagues = sorted(
        {
            str(e.get("league") or "").upper()
            for e in merged_events
            if e.get("league")
        }
    )

    if primary is None:
        payload: dict[str, Any] = {
            "event_id": "UNKNOWN",
            "sport": "UNKNOWN",
            "league": "UNKNOWN",
            "teams": [],
            "markets": flat_markets,
        }
    else:
        payload = {
            "event_id": primary.get("event_id", "UNKNOWN"),
            "sport": primary.get("sport", "UNKNOWN"),
            "league": primary.get("league", "UNKNOWN"),
            "teams": list(primary.get("teams") or []),
            "markets": flat_markets,
            "slate_event_count": len(merged_events),
            "slate_leagues": leagues,
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
        "source_refs": {
            "source": "FIXTURE",
            "day": day_name,
            "event_count": len(merged_events),
            "market_count": len(flat_markets),
            "leagues": leagues,
        },
        "payload": payload,
    }

    return {
        "meta": meta,
        "events": merged_events,
        "markets": markets,
        "ingest_payload": ingest_payload,
    }
