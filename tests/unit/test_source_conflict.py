from hollersports.sources.source_conflict import (
    detect_event_conflicts,
    join_events_by_teams,
)


def test_clear_when_teams_match():
    left = [{"event_id": "1", "teams": ["BOS", "LAL"]}]
    right = [{"event_id": "1", "teams": ["lal", "bos"]}]
    pkt = detect_event_conflicts(
        left_events=left,
        right_events=right,
        left_source="ESPN",
        right_source="ODDS",
    )
    assert pkt["status"] == "CLEAR"
    assert pkt["conflict_count"] == 0
    assert pkt["capital_authority"] is False


def test_conflict_on_team_mismatch():
    left = [{"event_id": "1", "teams": ["BOS", "LAL"]}]
    right = [{"event_id": "1", "teams": ["GSW", "PHX"]}]
    pkt = detect_event_conflicts(
        left_events=left,
        right_events=right,
        left_source="ESPN",
        right_source="ODDS",
    )
    assert pkt["status"] == "CONFLICT"
    assert pkt["conflict_count"] == 1
    assert pkt["conflicts"][0]["kind"] == "team_set_mismatch"


def test_clear_when_ids_diverge_but_teams_match():
    """Team-set join bridges ESPN id vs Odds id (not id-equality only)."""
    left = [
        {
            "event_id": "espn-1",
            "teams": ["BOS", "LAL"],
            "start_time": "2026-04-24T23:00:00Z",
        }
    ]
    right = [
        {
            "event_id": "odds-99",
            "teams": ["BOS", "LAL"],
            "start_time": "2026-04-24T23:05:00Z",
        }
    ]
    pkt = detect_event_conflicts(
        left_events=left,
        right_events=right,
        left_source="ESPN",
        right_source="ODDS",
    )
    assert pkt["status"] == "CLEAR"
    assert pkt["left_only_event_ids"] == []
    assert pkt["right_only_event_ids"] == []
    assert pkt["provenance"]["matched_count"] == 1
    kinds = {j["match_kind"] for j in pkt["joins"]}
    assert "teams_start" in kinds


def test_partial_when_teams_truly_unmatched():
    left = [{"event_id": "1", "teams": ["BOS", "LAL"]}]
    right = [{"event_id": "2", "teams": ["GSW", "PHX"]}]
    pkt = detect_event_conflicts(
        left_events=left,
        right_events=right,
        left_source="ESPN",
        right_source="ODDS",
    )
    assert pkt["status"] == "PARTIAL"
    assert "1" in pkt["left_only_event_ids"]
    assert "2" in pkt["right_only_event_ids"]


def test_join_events_by_teams_multi_game_proximity():
    left = [
        {
            "event_id": "e1",
            "teams": ["BOS", "LAL"],
            "start_time": "2026-04-24T23:00:00Z",
        },
        {
            "event_id": "e2",
            "teams": ["GSW", "PHX"],
            "start_time": "2026-04-25T01:30:00Z",
        },
    ]
    right = [
        {
            "event_id": "o-gsw",
            "teams": ["phx", "gsw"],
            "start_time": "2026-04-25T01:35:00Z",
        },
        {
            "event_id": "o-bos",
            "teams": ["LAL", "BOS"],
            "start_time": "2026-04-24T23:02:00Z",
        },
    ]
    joins = join_events_by_teams(left, right)
    matched = [j for j in joins if j["match_kind"] in {"teams_start", "event_id"}]
    assert len(matched) == 2
    by_left = {j["left_event_id"]: j["right_event_id"] for j in matched}
    assert by_left["e1"] == "o-bos"
    assert by_left["e2"] == "o-gsw"
    assert all(j["start_delta_seconds"] is not None for j in matched)
    assert all(j["start_delta_seconds"] < 600 for j in matched)


def test_join_rejects_far_start_times():
    left = [
        {
            "event_id": "e1",
            "teams": ["BOS", "LAL"],
            "start_time": "2026-04-24T23:00:00Z",
        }
    ]
    right = [
        {
            "event_id": "o1",
            "teams": ["BOS", "LAL"],
            "start_time": "2026-05-01T23:00:00Z",
        }
    ]
    joins = join_events_by_teams(left, right, max_start_delta_seconds=3600)
    kinds = {j["match_kind"] for j in joins}
    assert "left_only" in kinds
    assert "right_only" in kinds
