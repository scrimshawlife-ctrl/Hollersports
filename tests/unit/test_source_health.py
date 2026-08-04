from hollersports.runes.source_health import evaluate_source_health


def test_missing_provenance_fails():
    h = evaluate_source_health(
        {"event_id": "E1"},
        source_id="X",
        fetched_at="2026-04-24T12:00:00+00:00",
        current_time="2026-04-24T12:01:00+00:00",
        required_fields=["event_id"],
        source_refs=None,
    )
    assert h["status"] == "FAIL"
    assert h["authority"] == "SHADOW_ONLY"
    assert h["capital_authority"] is False


def test_fresh_pass():
    h = evaluate_source_health(
        {"event_id": "E1", "markets": []},
        source_id="FIXTURE",
        fetched_at="2026-04-24T12:00:00+00:00",
        current_time="2026-04-24T12:01:00+00:00",
        required_fields=["event_id"],
        source_refs={"source": "FIXTURE"},
    )
    assert h["status"] == "PASS"
