"""Cumulative settlement history bank for calibration."""

import pytest

from hollersports.paper.settlement_history import (
    GENESIS_PREV_HASH,
    append_settlement_history,
    calibration_entries_for_store,
    read_settlement_history,
    settlement_history_path,
)
from hollersports.runes.calibration_evaluator import evaluate_calibration

pytestmark = pytest.mark.calibration


def test_append_and_read_chain(tmp_path):
    written = append_settlement_history(
        tmp_path,
        [
            {
                "status": "WIN",
                "stake": 10,
                "pnl": 9,
                "strategy_id": "MARKET_CONSENSUS_EDGE",
                "entry_id": "e1",
            },
            {
                "status": "LOSS",
                "stake": 10,
                "pnl": -10,
                "strategy_id": "MARKET_CONSENSUS_EDGE",
                "entry_id": "e2",
            },
        ],
        run_id="R1",
        fixture="day001",
        recorded_at="2026-08-04T12:00:00Z",
    )
    assert len(written) == 2
    assert written[0]["prev_hash"] == GENESIS_PREV_HASH
    assert written[1]["prev_hash"] == written[0]["entry_hash"]
    assert written[0]["capital_authority"] is False

    rows = read_settlement_history(data_root=tmp_path)
    assert len(rows) == 2
    assert rows[0]["fixture"] == "day001"
    assert settlement_history_path(tmp_path).is_file()


def test_pending_skipped_when_settled_only(tmp_path):
    append_settlement_history(
        tmp_path,
        [
            {"status": "PENDING", "stake": 10, "pnl": 0, "entry_id": "p"},
            {"status": "WIN", "stake": 10, "pnl": 9, "entry_id": "w"},
        ],
        run_id="R",
    )
    assert len(read_settlement_history(data_root=tmp_path, settled_only=True)) == 1
    assert len(read_settlement_history(data_root=tmp_path, settled_only=False)) == 2


def test_cumulative_feeds_calibration(tmp_path, settled_sample_reliable):
    append_settlement_history(tmp_path, settled_sample_reliable, run_id="BANK")
    entries = calibration_entries_for_store(tmp_path, last_batch=[])
    assert len(entries) == 20
    cal = evaluate_calibration(entries, allow_forecast_weighting=True)
    assert cal["status"] == "RELIABLE"
    assert cal["model_edge_allowed"] is True


def test_fallback_to_last_batch(tmp_path):
    last = [{"status": "WIN", "stake": 5, "pnl": 4}]
    entries = calibration_entries_for_store(tmp_path, last)
    assert len(entries) == 1
