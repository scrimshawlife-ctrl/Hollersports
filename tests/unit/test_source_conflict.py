from hollersports.sources.source_conflict import detect_event_conflicts


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


def test_partial_when_ids_diverge():
    left = [{"event_id": "1", "teams": ["BOS", "LAL"]}]
    right = [{"event_id": "2", "teams": ["BOS", "LAL"]}]
    pkt = detect_event_conflicts(
        left_events=left,
        right_events=right,
        left_source="ESPN",
        right_source="ODDS",
    )
    assert pkt["status"] == "PARTIAL"
