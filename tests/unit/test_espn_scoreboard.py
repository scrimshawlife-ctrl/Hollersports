from hollersports.sources.espn_scoreboard import normalize_espn_scoreboard


def test_normalize_espn_scoreboard_minimal():
    raw = {
        "sport": "BASKETBALL",
        "events": [
            {
                "id": "401",
                "date": "2026-04-24T23:00:00Z",
                "status": {"type": {"name": "STATUS_SCHEDULED"}},
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
    events = normalize_espn_scoreboard(raw, league="NBA")
    assert len(events) == 1
    assert events[0]["event_id"] == "401"
    assert events[0]["league"] == "NBA"
    assert events[0]["teams"] == ["BOS", "LAL"]
    assert events[0]["source_refs"]["source"] == "ESPN_SCOREBOARD"
    assert "recommendation" not in events[0]
