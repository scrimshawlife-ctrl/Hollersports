"""ESPN scoreboard normalize + optional fetch (advisory ingest only)."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Public ESPN site API (no key). Respect rate limits; prefer fixtures in CI.
_ESPN_NBA = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"


def normalize_espn_scoreboard(raw: Mapping[str, Any], *, league: str = "NBA") -> list[dict[str, Any]]:
    """Normalize ESPN scoreboard JSON to Holler event dicts (no recommendations)."""
    events_out: list[dict[str, Any]] = []
    for event in raw.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions else {}
        if not isinstance(competition, Mapping):
            competition = {}
        competitors = competition.get("competitors") or []
        teams: list[str] = []
        for c in competitors:
            if not isinstance(c, Mapping):
                continue
            team = c.get("team") or {}
            if isinstance(team, Mapping):
                name = team.get("abbreviation") or team.get("displayName")
                if name:
                    teams.append(str(name))
        events_out.append(
            {
                "event_id": str(event.get("id") or "UNKNOWN"),
                "sport": str(raw.get("sport") or "BASKETBALL"),
                "league": league,
                "teams": teams,
                "start_time": event.get("date"),
                "status": (event.get("status") or {}).get("type", {}).get("name")
                if isinstance(event.get("status"), Mapping)
                else None,
                "source_refs": {
                    "source": "ESPN_SCOREBOARD",
                    "event_id": event.get("id"),
                    "role": "TRUTH",
                },
            }
        )
    return events_out


def fetch_espn_nba_scoreboard(*, timeout_s: float = 15.0) -> dict[str, Any]:
    """Fetch live NBA scoreboard. Network optional — not used in CI.

    Returns raw JSON dict or raises OSError/URLError/HTTPError.
    """
    req = Request(
        _ESPN_NBA,
        headers={"User-Agent": "HollerSports-advisory/0.2 (no-money; research)"},
    )
    with urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — fixed HTTPS public API
        import json

        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("espn_scoreboard_not_object")
    data.setdefault("sport", "BASKETBALL")
    return data
