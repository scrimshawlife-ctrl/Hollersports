from hollersports.sources.espn_outcomes import (
    merge_espn_moneyline_results,
    normalize_espn_moneyline_results,
)


def _final_event(
    event_id: str,
    *,
    teams: list[str],
    scores: list[str],
    winners: list[bool | None],
    status_name: str = "STATUS_FINAL",
    completed: bool = True,
) -> dict:
    competitors = []
    for i, team in enumerate(teams):
        row: dict = {
            "team": {"abbreviation": team},
            "score": scores[i] if i < len(scores) else None,
            "homeAway": "home" if i == 0 else "away",
        }
        if i < len(winners) and winners[i] is not None:
            row["winner"] = winners[i]
        competitors.append(row)
    return {
        "id": event_id,
        "date": "2026-04-24T23:00:00Z",
        "status": {"type": {"name": status_name, "completed": completed, "state": "post" if completed else "pre"}},
        "competitions": [{"competitors": competitors}],
    }


def test_normalize_espn_finals_moneyline_win_loss():
    raw = {
        "sport": "BASKETBALL",
        "events": [
            _final_event(
                "401",
                teams=["BOS", "LAL"],
                scores=["110", "100"],
                winners=[True, False],
            )
        ],
    }
    rows = normalize_espn_moneyline_results(raw, league="NBA")
    assert len(rows) == 2
    by_sel = {r["selection"]: r for r in rows}
    assert by_sel["BOS"]["result"] == "WIN"
    assert by_sel["LAL"]["result"] == "LOSS"
    assert by_sel["BOS"]["final_score"] == "110-100"
    assert by_sel["BOS"]["source"] == "ESPN_SCOREBOARD"
    assert by_sel["BOS"]["event_id"] == "401"


def test_normalize_espn_scheduled_is_pending():
    raw = {
        "sport": "BASKETBALL",
        "events": [
            _final_event(
                "402",
                teams=["GSW", "PHX"],
                scores=["", ""],
                winners=[None, None],
                status_name="STATUS_SCHEDULED",
                completed=False,
            )
        ],
    }
    # Override status to pre-game
    raw["events"][0]["status"] = {
        "type": {"name": "STATUS_SCHEDULED", "completed": False, "state": "pre"}
    }
    rows = normalize_espn_moneyline_results(raw, league="NBA")
    assert len(rows) == 2
    assert all(r["result"] == "PENDING" for r in rows)
    assert all(r["settled_at"] == "" for r in rows)


def test_normalize_espn_tie_is_push():
    raw = {
        "sport": "FOOTBALL",
        "events": [
            _final_event(
                "nfl-1",
                teams=["KC", "BUF"],
                scores=["24", "24"],
                winners=[None, None],
            )
        ],
    }
    rows = normalize_espn_moneyline_results(raw, league="NFL")
    assert all(r["result"] == "PUSH" for r in rows)


def test_merge_espn_moneyline_results_multi_league():
    nba = {
        "events": [
            _final_event("nba-1", teams=["BOS", "LAL"], scores=["1", "0"], winners=[True, False])
        ]
    }
    nhl = {
        "events": [
            _final_event("nhl-1", teams=["TOR", "MTL"], scores=["3", "2"], winners=[True, False])
        ]
    }
    rows = merge_espn_moneyline_results([(nba, "NBA"), (nhl, "NHL")])
    assert len(rows) == 4
    leagues = {r["league"] for r in rows}
    assert leagues == {"NBA", "NHL"}
