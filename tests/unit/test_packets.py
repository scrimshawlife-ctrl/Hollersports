import pytest
from pydantic import ValidationError

from hollersports.schemas.packets import (
    ExecutionPacket,
    SourceHealthPacket,
    StrategyCandidatePacket,
)
from hollersports.schemas.validate import validate_packet


def test_source_health_roundtrip():
    p = SourceHealthPacket(
        status="PASS",
        source_id="FIXTURE",
        freshness_seconds=10,
        missing_required_fields=[],
        stale=False,
        provenance_present=True,
        health_score=1.0,
    )
    d = p.model_dump()
    assert d["authority"] == "SHADOW_ONLY"
    assert d["capital_authority"] is False
    validate_packet(d, "SourceHealthPacket.v1")


def test_candidate_always_shadow():
    c = StrategyCandidatePacket(
        status="CANDIDATE",
        run_id="R1",
        strategy_id="MARKET_CONSENSUS_EDGE",
        strategy_family="CONSENSUS",
        event_id="E1",
        market_id="M1",
        selection="HOME_ML",
        score=0.7,
        confidence=0.7,
        features={"consensus_score": 0.7},
        packet_refs={"market_ingestion": "R1"},
    )
    assert c.authority == "SHADOW_ONLY"


def test_execution_mode_forbids_live_approved():
    """LIVE_APPROVED is not a constructible v1 execution mode."""
    with pytest.raises(ValidationError):
        ExecutionPacket(status="APPROVED_FOR_PAPER", run_id="R1", mode="LIVE_APPROVED")

    paper = ExecutionPacket(
        status="APPROVED_FOR_PAPER",
        run_id="R1",
        mode="PAPER_ONLY",
        capital_authority=False,
        execution_authority=False,
    )
    d = paper.model_dump()
    assert d["mode"] == "PAPER_ONLY"
    validate_packet(d, "ExecutionPacket.v1")

    live_mode_dict = {
        **d,
        "mode": "LIVE_APPROVED",
    }
    with pytest.raises(Exception):
        validate_packet(live_mode_dict, "ExecutionPacket.v1")
