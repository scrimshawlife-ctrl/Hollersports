"""Free-first closed operator day (injected; no network)."""

from hollersports.pipelines.free_first_day import run_free_first_operator_day
from hollersports.paper.settlement_history import (
    calibration_entries_for_store,
    read_settlement_history,
)


def _espn_event(eid: str, teams: list[str], date: str, *, final: bool = False) -> dict:
    comps = []
    for i, t in enumerate(teams):
        row = {
            "team": {"abbreviation": t},
            "homeAway": "home" if i == 0 else "away",
        }
        if final:
            row["score"] = "110" if i == 0 else "100"
            row["winner"] = i == 0
        comps.append(row)
    return {
        "id": eid,
        "date": date,
        "status": {
            "type": {
                "name": "STATUS_FINAL" if final else "STATUS_SCHEDULED",
                "completed": final,
                "state": "post" if final else "pre",
            }
        },
        "competitions": [{"competitors": comps}],
    }


def _odds_event(eid: str, home: str, away: str, commence: str) -> dict:
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
                            {"name": home, "price": -120},
                            {"name": away, "price": 100},
                        ],
                    }
                ],
            }
        ],
    }


def test_free_first_day_injected_writes_bank(tmp_path):
    espn = {
        "sport": "BASKETBALL",
        "events": [
            _espn_event("espn-a", ["BOS", "LAL"], "2026-04-24T23:00:00Z"),
        ],
    }
    odds = [
        _odds_event("odds-a", "BOS", "LAL", "2026-04-24T23:00:00Z"),
    ]
    finals = {
        "sport": "BASKETBALL",
        "events": [
            _espn_event("espn-a", ["BOS", "LAL"], "2026-04-24T23:00:00Z", final=True),
        ],
    }
    out = run_free_first_operator_day(
        data_root=tmp_path,
        run_id="FF-DAY-1",
        leagues=["NBA"],
        espn_raw=espn,
        odds_raw=odds,
        settle_espn_raw=finals,
        fetch_espn=True,
        fetch_odds=True,
        paper_top_n=10,
    )
    assert out["capital_authority"] is False
    assert out["execution_authority"] is False
    assert out["ingest_count"] >= 1
    assert out["status"] == "OBSERVED"
    # Bank may include PENDING and/or terminal; calibration collapses.
    raw = read_settlement_history(data_root=tmp_path, settled_only=False)
    assert len(raw) >= 1
    cal = calibration_entries_for_store(tmp_path)
    # Terminal WIN/LOSS for moneyline selections that papered.
    assert all(e["status"] in {"WIN", "LOSS", "PUSH", "VOID"} for e in cal)


def test_free_first_day_pending_then_resettle_collapses(tmp_path):
    espn = {
        "sport": "BASKETBALL",
        "events": [
            _espn_event("espn-b", ["BOS", "LAL"], "2026-04-24T23:00:00Z"),
        ],
    }
    odds = [_odds_event("odds-b", "BOS", "LAL", "2026-04-24T23:00:00Z")]
    scheduled = {
        "sport": "BASKETBALL",
        "events": [
            _espn_event("espn-b", ["BOS", "LAL"], "2026-04-24T23:00:00Z", final=False),
        ],
    }
    first = run_free_first_operator_day(
        data_root=tmp_path,
        run_id="FF-PEND",
        leagues=["NBA"],
        espn_raw=espn,
        odds_raw=odds,
        settle_espn_raw=scheduled,
        fetch_espn=True,
        fetch_odds=True,
        paper_top_n=10,
    )
    assert first["settlement_count"] >= 1
    assert len(calibration_entries_for_store(tmp_path)) == 0

    finals = {
        "sport": "BASKETBALL",
        "events": [
            _espn_event("espn-b", ["BOS", "LAL"], "2026-04-24T23:00:00Z", final=True),
        ],
    }
    second = run_free_first_operator_day(
        data_root=tmp_path,
        run_id="FF-FINAL",
        leagues=["NBA"],
        espn_raw=espn,
        odds_raw=odds,
        settle_espn_raw=finals,
        fetch_espn=True,
        fetch_odds=True,
        paper_top_n=10,
    )
    assert second["bank_written"] >= 1
    # Different run_ids → different entry_ids; sample grows with terminal rows only.
    cal = calibration_entries_for_store(tmp_path)
    assert len(cal) >= 1
    assert all(e["status"] in {"WIN", "LOSS", "PUSH", "VOID"} for e in cal)
