"""The Odds API normalize + optional fetch (advisory odds observation only)."""

from __future__ import annotations

import json
import os
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# https://the-odds-api.com/ — free tier key via THE_ODDS_API_KEY. Never place bets.
_ODDS_BASE = "https://api.the-odds-api.com/v4/sports"

# Day-one leagues → The Odds API sport keys (aligned with ESPN_LEAGUE_PATHS).
ODDS_LEAGUE_SPORT_KEYS: dict[str, str] = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "MLS": "soccer_usa_mls",
    "EPL": "soccer_epl",
}


def odds_sport_key_for_league(league: str) -> str:
    """Return The Odds API sport key for a day-one league label."""
    key = str(league or "").strip().upper()
    if key not in ODDS_LEAGUE_SPORT_KEYS:
        supported = ", ".join(sorted(ODDS_LEAGUE_SPORT_KEYS))
        raise ValueError(f"unsupported_odds_league:{league!r}; supported={supported}")
    return ODDS_LEAGUE_SPORT_KEYS[key]


def _american_to_decimal(price: Any) -> float | None:
    try:
        am = float(price)
    except (TypeError, ValueError):
        return None
    if am >= 100:
        return round(1.0 + am / 100.0, 4)
    if am <= -100:
        return round(1.0 + 100.0 / abs(am), 4)
    # already decimal-like
    if am > 1.0:
        return round(am, 4)
    return None


def normalize_odds_api_events(
    raw_events: Sequence[Mapping[str, Any]],
    *,
    sport_key: str = "basketball_nba",
    league: str = "NBA",
) -> list[dict[str, Any]]:
    """Normalize The Odds API event list to Holler markets (observation only)."""
    out: list[dict[str, Any]] = []
    for event in raw_events:
        if not isinstance(event, Mapping):
            continue
        event_id = str(event.get("id") or "UNKNOWN")
        home = str(event.get("home_team") or "")
        away = str(event.get("away_team") or "")
        teams = [t for t in (away, home) if t]
        commence = event.get("commence_time")
        bookmakers = event.get("bookmakers") or []
        markets: list[dict[str, Any]] = []
        prices: list[float] = []

        for book in bookmakers:
            if not isinstance(book, Mapping):
                continue
            book_key = str(book.get("key") or book.get("title") or "UNKNOWN")
            for market in book.get("markets") or []:
                if not isinstance(market, Mapping):
                    continue
                mkey = str(market.get("key") or "UNKNOWN")
                market_type = {
                    "h2h": "MONEYLINE",
                    "spreads": "SPREAD",
                    "totals": "TOTAL",
                }.get(mkey, mkey.upper())
                for outcome in market.get("outcomes") or []:
                    if not isinstance(outcome, Mapping):
                        continue
                    name = str(outcome.get("name") or "UNKNOWN")
                    price_am = outcome.get("price")
                    decimal = _american_to_decimal(price_am)
                    if decimal is not None:
                        prices.append(decimal)
                    point = outcome.get("point")
                    markets.append(
                        {
                            "market_id": f"{event_id}:{book_key}:{mkey}:{name}:{point}",
                            "market_type": market_type,
                            "selection": name,
                            "price": decimal if decimal is not None else price_am,
                            "point": point,
                            "sportsbook": book_key,
                            "source_refs": {
                                "source": "THE_ODDS_API",
                                "event_id": event_id,
                                "book": book_key,
                                "market_key": mkey,
                            },
                        }
                    )

        consensus = None
        if prices:
            consensus = round(sum(prices) / len(prices), 4)
            # attach a soft consensus score in [0,1] from price agreement (tight = higher)
            if len(prices) >= 2:
                spread = max(prices) - min(prices)
                consensus_score = max(0.0, min(1.0, 1.0 - spread / 0.5))
            else:
                consensus_score = 0.5
            for m in markets:
                if m.get("market_type") == "MONEYLINE" and m.get("consensus_score") is None:
                    m["consensus_score"] = consensus_score

        # Cross-book odds_history / odds_delta (never invents prices).
        from hollersports.sources.odds_movement import enrich_markets_cross_book

        for m in markets:
            m.setdefault("event_id", event_id)
        markets = enrich_markets_cross_book(markets)

        out.append(
            {
                "event_id": event_id,
                "sport": sport_key,
                "league": league,
                "teams": teams,
                "start_time": commence,
                "markets": markets,
                "consensus_decimal_mean": consensus,
                "source_refs": {
                    "source": "THE_ODDS_API",
                    "event_id": event_id,
                    "role": "ODDS",
                    "sport_key": sport_key,
                },
            }
        )
    return out


def odds_api_key_configured() -> bool:
    return bool(os.environ.get("THE_ODDS_API_KEY", "").strip())


def fetch_odds_api_odds(
    *,
    sport_key: str = "basketball_nba",
    regions: str = "us",
    markets: str = "h2h,spreads,totals",
    odds_format: str = "american",
    timeout_s: float = 20.0,
) -> list[dict[str, Any]]:
    """Fetch odds when THE_ODDS_API_KEY is set. Raises if key missing or HTTP fails.

    CI must not call this without mocking. Advisory observation only.
    """
    key = os.environ.get("THE_ODDS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("THE_ODDS_API_KEY not set")

    qs = urlencode(
        {
            "apiKey": key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
    )
    url = f"{_ODDS_BASE}/{sport_key}/odds?{qs}"
    from hollersports.sources.http_cache import cached_get_json

    # Cache key includes full URL (api key present) — store under data/http_cache only.
    data = cached_get_json(
        url,
        ttl_seconds=120.0,
        timeout_s=timeout_s,
        headers={"User-Agent": "HollerSports-advisory/0.3 (no-money; research)"},
    )
    if not isinstance(data, list):
        raise ValueError("odds_api_response_not_list")
    return [e for e in data if isinstance(e, dict)]
