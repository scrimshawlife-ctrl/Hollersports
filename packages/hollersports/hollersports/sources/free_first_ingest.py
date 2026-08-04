"""Orchestrate free-first live observation packs (advisory only; fixture default in CI)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

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
from hollersports.sources.source_conflict import detect_event_conflicts


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_live_observation_pack(
    *,
    run_id: str | None = None,
    fetch_espn: bool = True,
    fetch_odds: bool = True,
    espn_raw: dict[str, Any] | None = None,
    odds_raw: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an observation pack from free-first sources.

    Prefer injecting ``espn_raw`` / ``odds_raw`` in tests. Network fetch is opt-in
    and never required for CI. Does not place bets or handle money.
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

    conflict = detect_event_conflicts(
        left_events=espn_events,
        right_events=odds_events,
        left_source="ESPN_SCOREBOARD",
        right_source="THE_ODDS_API",
        run_id=rid,
    )

    # Prefer odds events for market-bearing ingest; fall back to ESPN schedule-only.
    primary = odds_events[0] if odds_events else (espn_events[0] if espn_events else None)
    ingest = None
    if primary is not None:
        markets = list(primary.get("markets") or [])
        payload = {
            "run_id": rid,
            "source_id": "FREE_FIRST",
            "source_type": "UNKNOWN",
            "fetched_at": _now_iso(),
            "current_time": _now_iso(),
            "required_fields": ["event_id"],
            "source_refs": {
                "source": "FREE_FIRST",
                "espn_events": len(espn_events),
                "odds_events": len(odds_events),
            },
            "payload": {
                "event_id": primary.get("event_id"),
                "sport": primary.get("sport"),
                "league": primary.get("league"),
                "teams": primary.get("teams") or [],
                "markets": markets,
            },
            "stale_after_seconds": 3600,
        }
        ingest = run_market_ingestion(payload)

    pack = {
        "schema_version": "FreeFirstObservationPack.v1",
        "status": "OBSERVED" if (espn_events or odds_events) else "NOT_COMPUTABLE",
        "run_id": rid,
        "espn_event_count": len(espn_events),
        "odds_event_count": len(odds_events),
        "espn_events": espn_events,
        "odds_events": odds_events,
        "conflict": conflict,
        "ingest": ingest,
        "errors": errors,
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "provenance": {
            "odds_key_configured": odds_api_key_configured(),
            "env_has_odds_key": bool(os.environ.get("THE_ODDS_API_KEY")),
        },
    }
    assert_no_live_capital(pack)
    if pack.get("ingest"):
        assert_no_live_capital(pack["ingest"])
    return pack
