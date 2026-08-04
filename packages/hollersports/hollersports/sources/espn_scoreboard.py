"""ESPN scoreboard normalize + optional fetch (advisory ingest only)."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Public ESPN site API (no key). Respect rate limits; prefer fixtures in CI.
_ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Day-one leagues → ESPN path segments (sport/league) under _ESPN_BASE.
# Soccer uses ESPN league codes: usa.1 = MLS, eng.1 = EPL.
ESPN_LEAGUE_PATHS: dict[str, str] = {
    "NBA": "basketball/nba",
    "NFL": "football/nfl",
    "MLB": "baseball/mlb",
    "NHL": "hockey/nhl",
    "MLS": "soccer/usa.1",
    "EPL": "soccer/eng.1",
}

# Canonical sport label when raw payload omits top-level "sport".
_LEAGUE_SPORT: dict[str, str] = {
    "NBA": "BASKETBALL",
    "NFL": "FOOTBALL",
    "MLB": "BASEBALL",
    "NHL": "HOCKEY",
    "MLS": "SOCCER",
    "EPL": "SOCCER",
}

_USER_AGENT = "HollerSports-advisory/0.2 (no-money; research)"


def _normalize_league_key(league: str) -> str:
    key = str(league or "").strip().upper()
    if key not in ESPN_LEAGUE_PATHS:
        supported = ", ".join(sorted(ESPN_LEAGUE_PATHS))
        raise ValueError(f"unsupported_espn_league:{league!r}; supported={supported}")
    return key


def espn_scoreboard_url(league: str) -> str:
    """Return the public ESPN scoreboard URL for a day-one league."""
    path = ESPN_LEAGUE_PATHS[_normalize_league_key(league)]
    return f"{_ESPN_BASE}/{path}/scoreboard"


def normalize_espn_scoreboard(raw: Mapping[str, Any], *, league: str = "NBA") -> list[dict[str, Any]]:
    """Normalize ESPN scoreboard JSON to Holler event dicts (no recommendations)."""
    league_key = str(league or "NBA").strip().upper() or "NBA"
    default_sport = _LEAGUE_SPORT.get(league_key, "UNKNOWN")
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
                "sport": str(raw.get("sport") or default_sport),
                "league": league_key,
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


def fetch_espn_scoreboard(
    *,
    league: str = "NBA",
    timeout_s: float = 15.0,
    use_cache: bool = True,
    cache_ttl_seconds: float = 300.0,
) -> dict[str, Any]:
    """Fetch live ESPN scoreboard for a day-one league. Network optional — not used in CI.

    Returns raw JSON dict or raises OSError/URLError/HTTPError/ValueError.
    """
    league_key = _normalize_league_key(league)
    url = espn_scoreboard_url(league_key)
    if use_cache:
        from hollersports.sources.http_cache import cached_get_json

        data = cached_get_json(
            url,
            ttl_seconds=cache_ttl_seconds,
            timeout_s=timeout_s,
            headers={"User-Agent": _USER_AGENT},
        )
    else:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — fixed HTTPS public API
            import json

            data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("espn_scoreboard_not_object")
    data.setdefault("sport", _LEAGUE_SPORT[league_key])
    return data


def fetch_espn_nba_scoreboard(*, timeout_s: float = 15.0) -> dict[str, Any]:
    """Thin wrapper: fetch live NBA scoreboard (backward compatible)."""
    return fetch_espn_scoreboard(league="NBA", timeout_s=timeout_s)
