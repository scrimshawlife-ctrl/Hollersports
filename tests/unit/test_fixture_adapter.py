"""Fixture day adapter — multi-event slate markets."""

from pathlib import Path

import pytest

from hollersports.sources.fixture_adapter import load_fixture_day

pytestmark = pytest.mark.unit


def test_day001_includes_all_slate_markets(fixture_day001: Path):
    day = load_fixture_day(fixture_day001)
    markets = day["ingest_payload"]["payload"]["markets"]
    # day001 odds file has 7 markets across leagues — not only NBA primary
    assert len(markets) >= 6
    leagues = {str(m.get("league") or "") for m in markets}
    # Enrichment from events
    assert "NBA" in leagues or any(
        "NBA" in str(m.get("event_id") or "") for m in markets
    )
    assert day["ingest_payload"]["source_refs"]["market_count"] == len(markets)
    assert day["ingest_payload"]["source_refs"]["event_count"] >= 5


def test_day002_includes_model_fields_on_nba(fixture_day002: Path):
    day = load_fixture_day(fixture_day002)
    markets = day["ingest_payload"]["payload"]["markets"]
    assert len(markets) >= 6
    with_model = [m for m in markets if m.get("model_probability") is not None]
    assert len(with_model) >= 1


def test_day003_complete(fixtures_root: Path):
    path = fixtures_root / "day003"
    assert path.is_dir()
    day = load_fixture_day(path)
    assert day["ingest_payload"]["payload"]["markets"]
    assert day["meta"].get("run_id") == "FIX-DAY003"
