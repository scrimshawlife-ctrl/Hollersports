from hollersports.sources.free_first_ingest import (
    DAY_ONE_LEAGUES,
    build_live_observation_pack,
    free_first_to_operator_inputs,
    run_multi_event_ingest,
)


def _espn_event(eid: str, teams: list[str], date: str) -> dict:
    return {
        "id": eid,
        "date": date,
        "competitions": [
            {
                "competitors": [
                    {"team": {"abbreviation": teams[0]}},
                    {"team": {"abbreviation": teams[1]}},
                ]
            }
        ],
    }


def _odds_event(
    eid: str,
    home: str,
    away: str,
    commence: str,
    *,
    home_price: int = -120,
    away_price: int = 100,
) -> dict:
    return {
        "id": eid,
        "home_team": home,
        "away_team": away,
        "commence_time": commence,
        "bookmakers": [
            {
                "key": "book_a",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": home, "price": home_price},
                            {"name": away, "price": away_price},
                        ],
                    }
                ],
            }
        ],
    }


def test_free_first_pack_from_injected_raw():
    espn_raw = {
        "sport": "BASKETBALL",
        "events": [
            _espn_event("401", ["BOS", "LAL"], "2026-04-24T23:00:00Z"),
        ],
    }
    odds_raw = [
        _odds_event("401", "BOS", "LAL", "2026-04-24T23:00:00Z"),
    ]
    pack = build_live_observation_pack(
        run_id="T-LIVE-1",
        espn_raw=espn_raw,
        odds_raw=odds_raw,
    )
    assert pack["status"] == "OBSERVED"
    assert pack["espn_event_count"] == 1
    assert pack["odds_event_count"] == 1
    assert pack["capital_authority"] is False
    assert pack["mode"] == "ADVISORY_ONLY"
    assert pack["ingest"] is not None
    assert pack["ingest"]["status"] in ("INGESTED", "REJECTED", "NOT_COMPUTABLE")
    assert pack["conflict"]["status"] in ("CLEAR", "PARTIAL", "CONFLICT")
    assert pack["ingest_count"] == 1
    assert len(pack["ingests"]) == 1
    assert len(pack["operator_inputs"]) == 1


def test_free_first_not_computable_without_data(monkeypatch):
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)

    def _boom(**kwargs):
        raise RuntimeError("network_disabled")

    monkeypatch.setattr(
        "hollersports.sources.free_first_ingest.fetch_espn_scoreboard",
        _boom,
    )
    pack = build_live_observation_pack(
        run_id="T-EMPTY",
        fetch_odds=True,
        fetch_espn=True,
        leagues=["NBA"],
    )
    assert pack["status"] == "NOT_COMPUTABLE"
    assert pack["espn_event_count"] == 0
    assert any("espn" in e for e in pack["errors"])
    assert pack["ingest"] is None
    assert pack["ingests"] == []
    assert pack["provenance"]["leagues"] == ["NBA"]


def test_free_first_injected_defaults_to_nba_league():
    pack = build_live_observation_pack(
        run_id="T-NBA-DEFAULT",
        espn_raw={
            "sport": "BASKETBALL",
            "events": [_espn_event("401", ["BOS", "LAL"], "2026-04-24T23:00:00Z")],
        },
        odds_raw=[_odds_event("401", "BOS", "LAL", "2026-04-24T23:00:00Z")],
    )
    assert pack["provenance"]["leagues"] == ["NBA"]
    assert pack["espn_events"][0]["league"] == "NBA"


def test_free_first_single_league_filter_injected():
    pack = build_live_observation_pack(
        run_id="T-NFL-INJECT",
        leagues=["NFL"],
        espn_raw={
            "sport": "FOOTBALL",
            "events": [_espn_event("nfl-1", ["KC", "BUF"], "2026-09-14T17:00:00Z")],
        },
        odds_raw=[_odds_event("nfl-1", "KC", "BUF", "2026-09-14T17:00:00Z")],
    )
    assert pack["status"] == "OBSERVED"
    assert pack["provenance"]["leagues"] == ["NFL"]
    assert pack["espn_events"][0]["league"] == "NFL"
    assert pack["odds_events"][0]["league"] == "NFL"
    assert pack["odds_events"][0]["sport"] == "americanfootball_nfl"
    assert pack["capital_authority"] is False


def test_free_first_multi_league_live_fetch_monkeypatch(monkeypatch):
    """Two leagues fetched via patched scoreboard — no network."""
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)

    def fake_espn(*, league: str = "NBA", **_kwargs):
        if league == "NBA":
            return {
                "sport": "BASKETBALL",
                "events": [_espn_event("nba-1", ["BOS", "LAL"], "2026-04-24T23:00:00Z")],
            }
        if league == "NHL":
            return {
                "sport": "HOCKEY",
                "events": [_espn_event("nhl-1", ["BOS", "NYR"], "2026-04-24T23:30:00Z")],
            }
        raise RuntimeError(f"unexpected_league:{league}")

    monkeypatch.setattr(
        "hollersports.sources.free_first_ingest.fetch_espn_scoreboard",
        fake_espn,
    )
    pack = build_live_observation_pack(
        run_id="T-MULTI-LG",
        fetch_espn=True,
        fetch_odds=True,
        leagues=["NBA", "NHL"],
    )
    assert pack["status"] == "OBSERVED"
    assert pack["provenance"]["leagues"] == ["NBA", "NHL"]
    assert pack["espn_event_count"] == 2
    leagues = {e["league"] for e in pack["espn_events"]}
    assert leagues == {"NBA", "NHL"}
    assert any("odds:THE_ODDS_API_KEY_not_set" in e for e in pack["errors"])
    assert pack["capital_authority"] is False
    assert pack["execution_authority"] is False


def test_free_first_live_default_leagues_all_day_one(monkeypatch):
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    called: list[str] = []

    def fake_espn(*, league: str = "NBA", **_kwargs):
        called.append(league)
        return {"sport": "UNKNOWN", "events": []}

    monkeypatch.setattr(
        "hollersports.sources.free_first_ingest.fetch_espn_scoreboard",
        fake_espn,
    )
    pack = build_live_observation_pack(
        run_id="T-ALL",
        fetch_espn=True,
        fetch_odds=False,
    )
    assert set(called) == set(DAY_ONE_LEAGUES)
    assert pack["provenance"]["leagues"] == list(DAY_ONE_LEAGUES)


def test_multi_event_join_and_operator_inputs_no_network():
    """ESPN + Odds multi-game fixtures with divergent ids; join by teams + start."""
    espn_raw = {
        "sport": "BASKETBALL",
        "events": [
            _espn_event("espn-bos", ["BOS", "LAL"], "2026-04-24T23:00:00Z"),
            _espn_event("espn-gsw", ["GSW", "PHX"], "2026-04-25T02:00:00Z"),
            _espn_event("espn-mia", ["MIA", "NYK"], "2026-04-25T00:30:00Z"),
        ],
    }
    # Distinct Odds ids — must not rely on event_id equality.
    odds_raw = [
        _odds_event("odds-mia", "NYK", "MIA", "2026-04-25T00:32:00Z"),
        _odds_event("odds-lal", "LAL", "BOS", "2026-04-24T23:03:00Z"),
        _odds_event("odds-phx", "PHX", "GSW", "2026-04-25T02:05:00Z"),
    ]

    pack = build_live_observation_pack(
        run_id="T-MULTI",
        espn_raw=espn_raw,
        odds_raw=odds_raw,
    )

    assert pack["status"] == "OBSERVED"
    assert pack["espn_event_count"] == 3
    assert pack["odds_event_count"] == 3
    assert pack["conflict"]["status"] == "CLEAR"
    assert pack["provenance"]["multi_event"] is True
    assert pack["ingest_count"] == 3
    assert len(pack["ingests"]) == 3
    assert len(pack["operator_inputs"]) == 3

    match_kinds = {j["match_kind"] for j in pack["joins"]}
    assert "teams_start" in match_kinds
    assert "left_only" not in match_kinds
    assert "right_only" not in match_kinds

    # Primary ingest is first; all ingests are market-bearing from odds side.
    assert pack["ingest"] is pack["ingests"][0] or pack["ingest"] == pack["ingests"][0]
    event_ids = {p["payload"]["event_id"] for p in pack["operator_inputs"]}
    # Prefer odds event ids when markets present
    assert event_ids == {"odds-mia", "odds-lal", "odds-phx"}

    for p in pack["operator_inputs"]:
        assert p["source_id"] == "FREE_FIRST"
        assert p["payload"]["markets"]
        assert p.get("capital_authority") is not True
        assert "join" in p["source_refs"]

    for ing in pack["ingests"]:
        assert ing["capital_authority"] is False
        assert ing["execution_authority"] is False
        assert ing["status"] in ("INGESTED", "REJECTED", "NOT_COMPUTABLE")


def test_free_first_to_operator_inputs_from_pack():
    pack = build_live_observation_pack(
        run_id="T-OP",
        espn_raw={
            "sport": "BASKETBALL",
            "events": [
                _espn_event("e1", ["BOS", "LAL"], "2026-04-24T23:00:00Z"),
                _espn_event("e2", ["GSW", "PHX"], "2026-04-25T01:00:00Z"),
            ],
        },
        odds_raw=[
            _odds_event("o1", "BOS", "LAL", "2026-04-24T23:00:00Z"),
            _odds_event("o2", "GSW", "PHX", "2026-04-25T01:00:00Z"),
        ],
    )
    inputs = free_first_to_operator_inputs(pack)
    assert len(inputs) == 2
    # Re-ingest via documented multi-event helper
    ingests = run_multi_event_ingest(inputs)
    assert len(ingests) == 2
    assert all(i.get("capital_authority") is False for i in ingests)


def test_run_multi_event_ingest_empty():
    assert run_multi_event_ingest([]) == []
