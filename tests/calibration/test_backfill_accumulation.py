"""Multi-fixture accumulation grows calibration sample in a shared data root."""

from pathlib import Path

import pytest

from hollersports.paper.settlement_history import read_settlement_history
from hollersports.pipelines.operator_day import run_operator_day
from hollersports.runes.calibration_evaluator import evaluate_calibration

pytestmark = pytest.mark.calibration


def test_multi_day_accumulation(
    fixture_day001: Path, fixture_day002: Path, tmp_path: Path
):
    bank = tmp_path / "bank"
    bank.mkdir()
    total_settled = 0
    for day in (fixture_day001, fixture_day002):
        for i in range(3):
            # Per-run isolation for paper ledgers; manually share settlement bank
            from hollersports.paper.settlement_history import append_settlement_history

            out = run_operator_day(
                day,
                data_root=tmp_path / f"{day.name}-{i}",
                paper_top_n=50,
                accumulate_settlements=False,
            )
            entries = (out.get("settlements") or {}).get("entries") or []
            settled = [
                e
                for e in entries
                if str(e.get("status") or "").upper() in {"WIN", "LOSS", "PUSH", "VOID"}
            ]
            total_settled += len(settled)
            append_settlement_history(
                bank, settled, run_id=str(out["ingest"].get("run_id")), fixture=day.name
            )

    hist = read_settlement_history(data_root=bank)
    assert len(hist) == total_settled
    assert len(hist) >= 6  # both days × repeats × some paper
    cal = evaluate_calibration(hist, allow_forecast_weighting=True)
    assert cal["sample_size"] == len(hist)
    assert cal["status"] in {"UNRELIABLE", "WATCH", "RELIABLE"}
    assert cal["capital_authority"] is False
