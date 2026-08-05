import pytest

from hollersports.sources.espn_scoreboard import (
    ESPN_LEAGUE_PATHS,
    espn_scoreboard_url,
    fetch_espn_nba_scoreboard,
    fetch_espn_scoreboard,
    normalize_espn_scoreboard,
)


def _minimal_event(
    event_id: str,
    *,
    date: str,
    status: str,
    teams: list[str],
) -> dict:
    return {
        "id": event_id,
        "date": date,
        "status": {"type": {"name": status}},
        "competitions": [
            {
                "competitors": [{"team": {"abbreviation": t}} for t in teams],
            }
        ],
    }


def test_normalize_espn_scoreboard_nba_minimal():
    raw = {
        "sport": "BASKETBALL",
        "events": [
            _minimal_event(
                "401",
                date="2026-04-24T23:00:00Z",
                status="STATUS_SCHEDULED",
                teams=["BOS", "LAL"],
            )
        ],
    }
    events = normalize_espn_scoreboard(raw, league="NBA")
    assert len(events) == 1
    assert events[0]["event_id"] == "401"
    assert events[0]["league"] == "NBA"
    assert events[0]["sport"] == "BASKETBALL"
    assert events[0]["teams"] == ["BOS", "LAL"]
    assert events[0]["source_refs"]["source"] == "ESPN_SCOREBOARD"
    assert "recommendation" not in events[0]


def test_normalize_espn_scoreboard_nfl_minimal():
    """NFL fixture — sport inferred from league when raw omits top-level sport."""
    raw = {
        "events": [
            _minimal_event(
                "401547417",
                date="2026-09-13T17:00:00Z",
                status="STATUS_SCHEDULED",
                teams=["KC", "BUF"],
            )
        ],
    }
    events = normalize_espn_scoreboard(raw, league="NFL")
    assert len(events) == 1
    assert events[0]["event_id"] == "401547417"
    assert events[0]["league"] == "NFL"
    assert events[0]["sport"] == "FOOTBALL"
    assert events[0]["teams"] == ["KC", "BUF"]
    assert events[0]["status"] == "STATUS_SCHEDULED"
    assert events[0]["source_refs"]["source"] == "ESPN_SCOREBOARD"
    assert "recommendation" not in events[0]


def test_normalize_espn_scoreboard_mlb_and_nhl():
    mlb_raw = {
        "events": [
            _minimal_event(
                "401696001",
                date="2026-04-01T18:10:00Z",
                status="STATUS_SCHEDULED",
                teams=["NYY", "BOS"],
            )
        ],
    }
    nhl_raw = {
        "sport": "HOCKEY",
        "events": [
            _minimal_event(
                "401685001",
                date="2026-10-10T23:00:00Z",
                status="STATUS_SCHEDULED",
                teams=["TOR", "MTL"],
            )
        ],
    }
    mlb = normalize_espn_scoreboard(mlb_raw, league="MLB")
    nhl = normalize_espn_scoreboard(nhl_raw, league="NHL")
    assert mlb[0]["league"] == "MLB" and mlb[0]["sport"] == "BASEBALL"
    assert mlb[0]["teams"] == ["NYY", "BOS"]
    assert nhl[0]["league"] == "NHL" and nhl[0]["sport"] == "HOCKEY"
    assert nhl[0]["teams"] == ["TOR", "MTL"]


def test_normalize_espn_scoreboard_soccer_mls_epl():
    mls_raw = {
        "events": [
            _minimal_event(
                "701001",
                date="2026-03-15T19:00:00Z",
                status="STATUS_SCHEDULED",
                teams=["LAFC", "SEA"],
            )
        ],
    }
    epl_raw = {
        "sport": "SOCCER",
        "events": [
            _minimal_event(
                "702001",
                date="2026-08-15T14:00:00Z",
                status="STATUS_SCHEDULED",
                teams=["ARS", "CHE"],
            )
        ],
    }
    mls = normalize_espn_scoreboard(mls_raw, league="MLS")
    epl = normalize_espn_scoreboard(epl_raw, league="epl")  # case-insensitive input
    assert mls[0]["league"] == "MLS" and mls[0]["sport"] == "SOCCER"
    assert epl[0]["league"] == "EPL" and epl[0]["sport"] == "SOCCER"
    assert epl[0]["teams"] == ["ARS", "CHE"]


def test_espn_league_paths_day_one():
    for league in ("NBA", "NFL", "MLB", "NHL", "MLS", "EPL"):
        assert league in ESPN_LEAGUE_PATHS
        url = espn_scoreboard_url(league)
        assert url.startswith("https://site.api.espn.com/apis/site/v2/sports/")
        assert url.endswith("/scoreboard")
        assert ESPN_LEAGUE_PATHS[league] in url


def test_espn_scoreboard_url_unsupported():
    with pytest.raises(ValueError, match="unsupported_espn_league"):
        espn_scoreboard_url("WNBA")


def test_fetch_espn_nba_is_thin_wrapper(monkeypatch):
    calls: list[dict] = []

    def fake_fetch(*, league: str = "NBA", timeout_s: float = 15.0):
        calls.append({"league": league, "timeout_s": timeout_s})
        return {"sport": "BASKETBALL", "events": []}

    monkeypatch.setattr(
        "hollersports.sources.espn_scoreboard.fetch_espn_scoreboard",
        fake_fetch,
    )
    out = fetch_espn_nba_scoreboard(timeout_s=9.0)
    assert out["sport"] == "BASKETBALL"
    assert calls == [{"league": "NBA", "timeout_s": 9.0}]


def test_fetch_espn_scoreboard_rejects_unknown_league():
    with pytest.raises(ValueError, match="unsupported_espn_league"):
        fetch_espn_scoreboard(league="XFL")
