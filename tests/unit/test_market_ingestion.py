from pathlib import Path

from hollersports.pipelines.market_ingestion import run_market_ingestion
from hollersports.sources.fixture_adapter import load_fixture_day


def test_fixture_ingest_ingested():
    day = load_fixture_day(Path("fixtures/day001"))
    packet = run_market_ingestion(day["ingest_payload"])
    assert packet["status"] == "INGESTED"
    assert packet["authority"] == "SHADOW_ONLY"
    assert "recommendation" not in packet
    assert len(packet["markets"]) >= 1
    assert packet["capital_authority"] is False


def test_source_fail_rejects_with_empty_markets():
    packet = run_market_ingestion(
        {
            "run_id": "R-FAIL",
            "source_id": "X",
            "source_type": "MANUAL",
            "fetched_at": "2026-04-24T12:00:00+00:00",
            "current_time": "2026-04-24T12:01:00+00:00",
            "required_fields": ["event_id"],
            "source_refs": None,
            "payload": {"event_id": "E1", "markets": [{"market_id": "M1"}]},
        }
    )
    assert packet["status"] == "REJECTED"
    assert packet["markets"] == []
    assert "recommendation" not in packet
    assert packet["capital_authority"] is False


def test_invalid_timestamps_not_computable_ingest():
    packet = run_market_ingestion(
        {
            "run_id": "R-NC",
            "source_id": "X",
            "source_type": "MANUAL",
            "fetched_at": "bad",
            "current_time": "worse",
            "required_fields": ["event_id"],
            "source_refs": {"source": "X"},
            "payload": {"event_id": "E1", "markets": []},
        }
    )
    assert packet["status"] == "NOT_COMPUTABLE"
    assert packet["markets"] == []
    assert "recommendation" not in packet
