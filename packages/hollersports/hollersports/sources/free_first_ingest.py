"""Orchestrate free-first live observation packs (advisory only; fixture default in CI).

Multi-event note
----------------
``MarketIngestionPacket.v1`` is **single-event** (one ``event_id`` / ``teams`` /
``markets`` slate row). Free-first observation can see a multi-game day, so this
module:

* joins ESPN + Odds events by ``event_id`` or normalized team set + start proximity
* builds **one ingest payload per event** via :func:`free_first_to_operator_inputs`
* runs them with :func:`run_multi_event_ingest` (documented multi-event helper)

``build_live_observation_pack`` keeps ``ingest`` as the first event for backward
compatibility and adds ``ingests`` (full list). Never places bets or handles money.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from hollersports.governance.authority import assert_no_live_capital
from hollersports.pipelines.market_ingestion import run_market_ingestion
from hollersports.sources.espn_scoreboard import (
    fetch_espn_nba_scoreboard,
    normalize_espn_scoreboard,
)
from hollersports.sources.odds_api import (
    fetch_odds_api_odds,
    normalize_odds_api_events,
    odds_api_key_configured,
)
from hollersports.sources.source_conflict import (
    detect_event_conflicts,
    join_events_by_teams,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _event_to_ingest_payload(
    event: Mapping[str, Any],
    *,
    run_id: str,
    espn_count: int,
    odds_count: int,
    join_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a single-event market-ingestion request dict (advisory)."""
    markets = list(event.get("markets") or [])
    # Tag markets with event_id when missing so multi-event competition stays keyed.
    eid = str(event.get("event_id") or "UNKNOWN")
    tagged_markets: list[dict[str, Any]] = []
    for m in markets:
        if not isinstance(m, Mapping):
            continue
        row = dict(m)
        row.setdefault("event_id", eid)
        tagged_markets.append(row)

    payload_body: dict[str, Any] = {
        "event_id": eid,
        "sport": event.get("sport") or "UNKNOWN",
        "league": event.get("league") or "UNKNOWN",
        "teams": list(event.get("teams") or []),
        "markets": tagged_markets,
    }
    for key in ("home_team", "away_team", "start_time", "status", "commence_time"):
        if key in event and event[key] is not None:
            payload_body[key] = event[key]

    source_refs: dict[str, Any] = {
        "source": "FREE_FIRST",
        "espn_events": espn_count,
        "odds_events": odds_count,
    }
    if join_meta:
        source_refs["join"] = {
            "match_kind": join_meta.get("match_kind"),
            "left_event_id": join_meta.get("left_event_id"),
            "right_event_id": join_meta.get("right_event_id"),
            "team_set": join_meta.get("team_set"),
        }

    return {
        "run_id": run_id,
        "source_id": "FREE_FIRST",
        "source_type": "UNKNOWN",
        "fetched_at": _now_iso(),
        "current_time": _now_iso(),
        "required_fields": ["event_id"],
        "source_refs": source_refs,
        "payload": payload_body,
        "stale_after_seconds": 3600,
    }


def _primary_event_from_join(join: Mapping[str, Any]) -> dict[str, Any] | None:
    """Prefer odds (right) when markets exist; else ESPN (left); else right bare."""
    right = join.get("right")
    left = join.get("left")
    right_m = right if isinstance(right, Mapping) else None
    left_m = left if isinstance(left, Mapping) else None

    if right_m is not None and list(right_m.get("markets") or []):
        out = dict(right_m)
        # Enrich missing schedule fields from ESPN side.
        if left_m is not None:
            for key in ("start_time", "status", "sport", "league"):
                if out.get(key) in (None, "", "UNKNOWN") and left_m.get(key) is not None:
                    out[key] = left_m[key]
            if not out.get("teams") and left_m.get("teams"):
                out["teams"] = list(left_m["teams"])
        return out
    if left_m is not None:
        out = dict(left_m)
        if right_m is not None and list(right_m.get("markets") or []):
            out["markets"] = list(right_m["markets"])
            # Prefer odds event_id for market keys when left was schedule-only merge.
            if right_m.get("event_id"):
                out.setdefault("odds_event_id", right_m.get("event_id"))
        return out
    if right_m is not None:
        return dict(right_m)
    return None


def free_first_to_operator_inputs(
    pack: Mapping[str, Any] | None = None,
    *,
    espn_events: Sequence[Mapping[str, Any]] | None = None,
    odds_events: Sequence[Mapping[str, Any]] | None = None,
    run_id: str | None = None,
    joins: Sequence[Mapping[str, Any]] | None = None,
    max_start_delta_seconds: float = 12 * 3600,
) -> list[dict[str, Any]]:
    """Return one market-ingestion payload per free-first slate event.

    ``MarketIngestionPacket.v1`` is single-event, so a multi-game observation
    pack becomes a **list** of operator ingest payloads (not one merged packet).

    Sources of events (first non-empty path wins for lists):
      * explicit ``espn_events`` / ``odds_events`` kwargs
      * ``pack["espn_events"]`` / ``pack["odds_events"]``

    Joins use :func:`join_events_by_teams` unless ``joins`` is provided.
    Prefer odds-bearing rows; fall back to ESPN schedule-only.
    """
    if pack is not None and not isinstance(pack, Mapping):
        pack = None

    espn = list(espn_events) if espn_events is not None else list(
        (pack or {}).get("espn_events") or []
    )
    odds = list(odds_events) if odds_events is not None else list(
        (pack or {}).get("odds_events") or []
    )
    rid = str(
        run_id
        or (pack or {}).get("run_id")
        or f"LIVE-{_now_iso()}"
    )

    if joins is None:
        join_rows = join_events_by_teams(
            espn,
            odds,
            max_start_delta_seconds=max_start_delta_seconds,
        )
    else:
        join_rows = [j for j in joins if isinstance(j, Mapping)]

    # No joins at all (empty sides): still emit from whichever side has events.
    if not join_rows:
        events: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
        for e in odds:
            if isinstance(e, Mapping):
                events.append((dict(e), None))
        if not events:
            for e in espn:
                if isinstance(e, Mapping):
                    events.append((dict(e), None))
        return [
            _event_to_ingest_payload(
                ev,
                run_id=rid if len(events) == 1 else f"{rid}:{ev.get('event_id')}",
                espn_count=len(espn),
                odds_count=len(odds),
                join_meta=meta,
            )
            for ev, meta in events
        ]

    payloads: list[dict[str, Any]] = []
    multi = len(join_rows) > 1
    for j in join_rows:
        primary = _primary_event_from_join(j)
        if primary is None:
            continue
        eid = str(primary.get("event_id") or "UNKNOWN")
        event_run_id = f"{rid}:{eid}" if multi else rid
        payloads.append(
            _event_to_ingest_payload(
                primary,
                run_id=event_run_id,
                espn_count=len(espn),
                odds_count=len(odds),
                join_meta=j,
            )
        )
    return payloads


def run_multi_event_ingest(
    payloads: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Ingest each free-first operator payload via :func:`run_market_ingestion`.

    Documented helper for multi-event free-first slates. Returns one
    MarketIngestionPacket-shaped dict per payload. Advisory only — no capital.
    """
    out: list[dict[str, Any]] = []
    for p in payloads:
        if not isinstance(p, Mapping):
            continue
        packet = run_market_ingestion(dict(p))
        assert_no_live_capital(packet)
        out.append(packet)
    return out


def build_live_observation_pack(
    *,
    run_id: str | None = None,
    fetch_espn: bool = True,
    fetch_odds: bool = True,
    espn_raw: dict[str, Any] | None = None,
    odds_raw: list[dict[str, Any]] | None = None,
    max_start_delta_seconds: float = 12 * 3600,
) -> dict[str, Any]:
    """Build an observation pack from free-first sources.

    Prefer injecting ``espn_raw`` / ``odds_raw`` in tests. Network fetch is opt-in
    and never required for CI. Multi-event days produce ``ingests`` (list) plus
    ``ingest`` (first element, backward compatible). Does not place bets or
    handle money.
    """
    rid = run_id or f"LIVE-{_now_iso()}"
    errors: list[str] = []
    espn_events: list[dict[str, Any]] = []
    odds_events: list[dict[str, Any]] = []

    if fetch_espn:
        try:
            raw = espn_raw if espn_raw is not None else fetch_espn_nba_scoreboard()
            espn_events = normalize_espn_scoreboard(raw, league="NBA")
        except Exception as exc:  # noqa: BLE001 — surface as PARTIAL observation
            errors.append(f"espn:{type(exc).__name__}:{exc}")

    if fetch_odds:
        try:
            if odds_raw is not None:
                raw_odds = odds_raw
            elif odds_api_key_configured():
                raw_odds = fetch_odds_api_odds()
            else:
                raw_odds = []
                errors.append("odds:THE_ODDS_API_KEY_not_set")
            if raw_odds:
                odds_events = normalize_odds_api_events(raw_odds, league="NBA")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"odds:{type(exc).__name__}:{exc}")

    joins = join_events_by_teams(
        espn_events,
        odds_events,
        max_start_delta_seconds=max_start_delta_seconds,
    )
    conflict = detect_event_conflicts(
        left_events=espn_events,
        right_events=odds_events,
        left_source="ESPN_SCOREBOARD",
        right_source="THE_ODDS_API",
        run_id=rid,
        max_start_delta_seconds=max_start_delta_seconds,
    )

    operator_inputs = free_first_to_operator_inputs(
        espn_events=espn_events,
        odds_events=odds_events,
        run_id=rid,
        joins=joins,
        max_start_delta_seconds=max_start_delta_seconds,
    )
    ingests = run_multi_event_ingest(operator_inputs) if operator_inputs else []
    ingest = ingests[0] if ingests else None

    join_summaries = [
        {
            "match_kind": j.get("match_kind"),
            "team_set": j.get("team_set"),
            "start_delta_seconds": j.get("start_delta_seconds"),
            "left_event_id": j.get("left_event_id"),
            "right_event_id": j.get("right_event_id"),
        }
        for j in joins
    ]

    pack = {
        "schema_version": "FreeFirstObservationPack.v1",
        "status": "OBSERVED" if (espn_events or odds_events) else "NOT_COMPUTABLE",
        "run_id": rid,
        "espn_event_count": len(espn_events),
        "odds_event_count": len(odds_events),
        "espn_events": espn_events,
        "odds_events": odds_events,
        "joins": join_summaries,
        "join_count": len(joins),
        "conflict": conflict,
        "operator_inputs": operator_inputs,
        "ingest": ingest,
        "ingests": ingests,
        "ingest_count": len(ingests),
        "errors": errors,
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "provenance": {
            "odds_key_configured": odds_api_key_configured(),
            "env_has_odds_key": bool(os.environ.get("THE_ODDS_API_KEY")),
            "multi_event": len(ingests) > 1,
            "max_start_delta_seconds": max_start_delta_seconds,
        },
    }
    assert_no_live_capital(pack)
    if pack.get("ingest"):
        assert_no_live_capital(pack["ingest"])
    for item in pack.get("ingests") or []:
        if isinstance(item, Mapping):
            assert_no_live_capital(item)
    return pack
