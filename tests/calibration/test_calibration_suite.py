"""End-to-end calibration framework: fixtures → settle → ladder → model edge."""

from __future__ import annotations

from pathlib import Path

import pytest

from hollersports.governance.gates import calibration_allows_model_edge
from hollersports.pipelines.operator_day import run_operator_day
from hollersports.pipelines.strategy_competition import run_strategy_competition
from hollersports.runes.calibration_evaluator import evaluate_calibration
from hollersports.schemas.hashing import packet_hash

pytestmark = [pytest.mark.calibration, pytest.mark.golden]


def test_operator_day_day001_yields_calibration_packet(
    fixture_day001: Path, tmp_path: Path
):
    out = run_operator_day(fixture_day001, data_root=tmp_path / "d1")
    entries = (out.get("settlements") or {}).get("entries") or []
    cal = evaluate_calibration(entries, allow_forecast_weighting=True)
    assert cal["schema_version"] == "CalibrationPacket.v1"
    assert cal["capital_authority"] is False
    assert cal["execution_authority"] is False
    # Small fixture paper top-N cannot be RELIABLE under default thresholds
    assert cal["status"] in {"EMPTY", "UNRELIABLE", "WATCH"}
    assert cal["model_edge_allowed"] is False


def test_multi_fixture_invariance(fixture_day001: Path, fixture_day002: Path, tmp_path: Path):
    """Each fixture day is deterministic across 3 runs (hash-stable cores)."""
    for name, day in (("day001", fixture_day001), ("day002", fixture_day002)):
        hashes: list[str] = []
        for i in range(3):
            out = run_operator_day(day, data_root=tmp_path / name / f"r{i}")
            core = {
                "ingest_status": out["ingest"]["status"],
                "candidates": out["competition"].get("candidates", []),
                "promotion_status": out["promotion"]["status"],
                "model_edge_enabled": out["competition"].get("model_edge_enabled"),
            }
            hashes.append(packet_hash(core))
            for key in ("ingest", "competition", "paper", "performance", "promotion"):
                pkt = out[key]
                assert pkt.get("capital_authority") is not True
                assert pkt.get("execution_authority") is not True
        assert len(set(hashes)) == 1, f"{name} not invariant: {hashes}"


def test_model_edge_gate_matrix_on_day002_ingest(
    fixture_day002: Path, tmp_path: Path, settled_sample_reliable: list
):
    """day002 markets have model fields; edge only when calibration allows."""
    out = run_operator_day(fixture_day002, data_root=tmp_path / "me")
    ingest = out["ingest"]
    assert ingest["status"] == "INGESTED"

    off = run_strategy_competition(ingest)
    assert off["model_edge_enabled"] is False
    assert all(
        c.get("strategy_id") != "MODEL_PROBABILITY_EDGE"
        for c in off.get("candidates") or []
    )

    # Manual RELIABLE without enough real history (operator override path)
    manual = run_strategy_competition(
        ingest,
        calibration={
            "allow_forecast_weighting": True,
            "reliability_status": "RELIABLE",
        },
    )
    assert manual["model_edge_enabled"] is True
    assert any(
        c.get("strategy_id") == "MODEL_PROBABILITY_EDGE"
        for c in manual.get("candidates") or []
    )

    # Evidence-based packet from synthetic reliable sample
    cal = evaluate_calibration(settled_sample_reliable, allow_forecast_weighting=True)
    assert calibration_allows_model_edge(cal) is True
    auto = run_strategy_competition(ingest, calibration=cal)
    assert auto["model_edge_enabled"] is True


def test_calibration_never_grants_capital(settled_sample_reliable: list):
    cal = evaluate_calibration(settled_sample_reliable, allow_forecast_weighting=True)
    assert cal["model_edge_allowed"] is True
    assert cal["capital_authority"] is False
    assert cal["execution_authority"] is False
