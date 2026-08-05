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


def test_missing_required_fields_fails():
    h = evaluate_source_health(
        {},
        source_id="X",
        fetched_at="2026-04-24T12:00:00+00:00",
        current_time="2026-04-24T12:01:00+00:00",
        required_fields=["event_id", "markets"],
        source_refs={"source": "X"},
    )
    assert h["status"] == "FAIL"
    assert "event_id" in h.get("missing_required_fields", [])


def test_stale_data_warns():
    h = evaluate_source_health(
        {"event_id": "E1"},
        source_id="X",
        fetched_at="2026-04-24T12:00:00+00:00",
        current_time="2026-04-24T12:30:00+00:00",  # 1800s later, default stale=900
        required_fields=["event_id"],
        source_refs={"source": "X"},
        stale_after_seconds=900,
    )
    assert h["status"] == "WARN"
    assert h["stale"] is True


def test_invalid_timestamps_not_computable():
    h = evaluate_source_health(
        {"event_id": "E1"},
        source_id="X",
        fetched_at="not-a-time",
        current_time="also-bad",
        required_fields=["event_id"],
        source_refs={"source": "X"},
    )
    assert h["status"] == "NOT_COMPUTABLE"


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
