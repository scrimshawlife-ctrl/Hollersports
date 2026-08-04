from hollersports.sources.free_first_ingest import build_live_observation_pack


def test_free_first_pack_from_injected_raw():
    espn_raw = {
        "sport": "BASKETBALL",
        "events": [
            {
                "id": "401",
                "date": "2026-04-24T23:00:00Z",
                "competitions": [
                    {
                        "competitors": [
                            {"team": {"abbreviation": "BOS"}},
                            {"team": {"abbreviation": "LAL"}},
                        ]
                    }
                ],
            }
        ],
    }
    odds_raw = [
        {
            "id": "401",
            "home_team": "BOS",
            "away_team": "LAL",
            "commence_time": "2026-04-24T23:00:00Z",
            "bookmakers": [
                {
                    "key": "book_a",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "BOS", "price": -120},
                                {"name": "LAL", "price": 100},
                            ],
                        }
                    ],
                }
            ],
        }
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


def test_free_first_not_computable_without_data(monkeypatch):
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)

    def _boom(**kwargs):
        raise RuntimeError("network_disabled")

    monkeypatch.setattr(
        "hollersports.sources.free_first_ingest.fetch_espn_nba_scoreboard",
        _boom,
    )
    pack = build_live_observation_pack(run_id="T-EMPTY", fetch_odds=True, fetch_espn=True)
    assert pack["status"] == "NOT_COMPUTABLE"
    assert pack["espn_event_count"] == 0
    assert any("espn" in e for e in pack["errors"])
