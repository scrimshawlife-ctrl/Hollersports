from hollersports.sources.odds_api import (
    normalize_odds_api_events,
    odds_api_key_configured,
    odds_sport_key_for_league,
)


def test_normalize_odds_api_moneyline():
    raw = [
        {
            "id": "evt1",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "commence_time": "2026-04-24T23:00:00Z",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": -140},
                                {"name": "Los Angeles Lakers", "price": 120},
                            ],
                        }
                    ],
                },
                {
                    "key": "fanduel",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Boston Celtics", "price": -135},
                                {"name": "Los Angeles Lakers", "price": 115},
                            ],
                        }
                    ],
                },
            ],
        }
    ]
    events = normalize_odds_api_events(raw, league="NBA")
    assert len(events) == 1
    assert events[0]["event_id"] == "evt1"
    assert len(events[0]["markets"]) == 4
    assert events[0]["source_refs"]["source"] == "THE_ODDS_API"
    assert "recommendation" not in events[0]
    ml = [m for m in events[0]["markets"] if m["market_type"] == "MONEYLINE"]
    assert all(m.get("consensus_score") is not None for m in ml)


def test_odds_key_configured_false_by_default(monkeypatch):
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    assert odds_api_key_configured() is False


def test_odds_sport_key_for_day_one_leagues():
    assert odds_sport_key_for_league("NBA") == "basketball_nba"
    assert odds_sport_key_for_league("nfl") == "americanfootball_nfl"
    assert odds_sport_key_for_league("EPL") == "soccer_epl"
    try:
        odds_sport_key_for_league("WNBA")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "unsupported_odds_league" in str(exc)
