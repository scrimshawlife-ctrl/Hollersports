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
