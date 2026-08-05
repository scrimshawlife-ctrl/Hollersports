"""Unit tests for CalibrationPacket evaluation and model-edge gates."""

import pytest

from hollersports.governance.gates import calibration_allows_model_edge
from hollersports.runes.calibration_evaluator import (
    DEFAULT_MIN_SAMPLE_RELIABLE,
    calibration_gate_from_packet,
    evaluate_calibration,
)

pytestmark = pytest.mark.calibration


def test_empty_settlements():
    p = evaluate_calibration([])
    assert p["status"] == "EMPTY"
    assert p["reliability_status"] == "UNRELIABLE"
    assert p["model_edge_allowed"] is False
    assert p["capital_authority"] is False
    assert p["execution_authority"] is False
    assert p["mode"] == "ADVISORY_ONLY"
    assert p["schema_version"] == "CalibrationPacket.v1"
    assert len(p["packet_hash"]) == 64


def test_unreliable_small_sample(settled_sample_unreliable):
    p = evaluate_calibration(settled_sample_unreliable)
    assert p["status"] == "UNRELIABLE"
    assert p["sample_size"] == 2
    assert p["model_edge_allowed"] is False


def test_watch_band(settled_sample_watch):
    p = evaluate_calibration(settled_sample_watch)
    assert p["status"] == "WATCH"
    assert p["reliability_status"] == "WATCH"
    assert p["sample_size"] == 8
    assert p["sample_size"] < DEFAULT_MIN_SAMPLE_RELIABLE
    # Even with allow flag, WATCH does not unlock model edge
    p2 = evaluate_calibration(settled_sample_watch, allow_forecast_weighting=True)
    assert p2["model_edge_allowed"] is False
    assert calibration_allows_model_edge(p2) is False


def test_reliable_and_model_edge(settled_sample_reliable):
    p = evaluate_calibration(settled_sample_reliable)
    assert p["status"] == "RELIABLE"
    assert p["reliability_status"] == "RELIABLE"
    assert p["sample_size"] >= DEFAULT_MIN_SAMPLE_RELIABLE
    assert p["hit_rate"] >= 0.45
    assert p["model_edge_allowed"] is False  # allow flag still required

    p2 = evaluate_calibration(
        settled_sample_reliable, allow_forecast_weighting=True
    )
    assert p2["model_edge_allowed"] is True
    assert calibration_allows_model_edge(p2) is True
    gate = calibration_gate_from_packet(p2)
    assert gate["allow_forecast_weighting"] is True
    assert gate["reliability_status"] == "RELIABLE"
    assert calibration_allows_model_edge(gate) is True


def test_pending_excluded():
    p = evaluate_calibration(
        [
            {"status": "PENDING", "stake": 10, "pnl": 0},
            {"status": "WIN", "stake": 10, "pnl": 9},
        ]
    )
    assert p["sample_size"] == 1
    assert p["status"] == "UNRELIABLE"


def test_gate_legacy_dict_still_works():
    assert (
        calibration_allows_model_edge(
            {"allow_forecast_weighting": True, "reliability_status": "RELIABLE"}
        )
        is True
    )
    assert (
        calibration_allows_model_edge(
            {"allow_forecast_weighting": True, "reliability_status": "WATCH"}
        )
        is False
    )
    assert calibration_allows_model_edge(None) is False


def test_deterministic_hash(settled_sample_reliable):
    a = evaluate_calibration(settled_sample_reliable, allow_forecast_weighting=True)
    b = evaluate_calibration(settled_sample_reliable, allow_forecast_weighting=True)
    assert a["packet_hash"] == b["packet_hash"]
