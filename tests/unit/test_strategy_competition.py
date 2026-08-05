from hollersports.pipelines.strategy_competition import (
    run_strategy_competition,
    run_strategy_competition_multi,
)

def _ingest(extra_market_fields: dict | None = None):
    market = {
        "market_id": "M1",
        "selection": "HOME_ML",
        "consensus_score": 0.8,
        "public_bet_pct": 0.75,
        "handle_pct": 0.5,
        "fade_selection": "AWAY_ML",
        "clv_retention": 0.02,
    }
    if extra_market_fields:
        market.update(extra_market_fields)
    return {
        "schema_version": "MarketIngestionPacket.v1",
        "status": "INGESTED",
        "run_id": "R1",
        "event_id": "E1",
        "markets": [market],
        "authority": "SHADOW_ONLY",
    }

def test_competition_emits_shadow_only_sorted():
    out = run_strategy_competition(_ingest())
    assert out["status"] == "COMPUTED"
    assert out["candidate_count"] >= 1
    for c in out["candidates"]:
        assert c["authority"] == "SHADOW_ONLY"
        assert c.get("capital_authority", False) is False

def test_invalid_ingest_not_computable():
    out = run_strategy_competition({"status": "REJECTED"})
    assert out["status"] == "NOT_COMPUTABLE"


def test_model_edge_absent_without_calibration():
    packet = _ingest(
        {
            "model_probability": 0.60,
            "market_implied_probability": 0.50,
        }
    )
    out = run_strategy_competition(packet)
    assert out["model_edge_enabled"] is False
    ids = [c["strategy_id"] for c in out["candidates"]]
    assert "MODEL_PROBABILITY_EDGE" not in ids
    assert "MODEL_PROBABILITY_EDGE" not in (out.get("provenance") or {}).get(
        "strategy_ids", []
    )


def test_model_edge_present_with_reliable_gate():
    packet = _ingest(
        {
            "model_probability": 0.60,
            "market_implied_probability": 0.50,
        }
    )
    cal = {"allow_forecast_weighting": True, "reliability_status": "RELIABLE"}
    out = run_strategy_competition(packet, calibration=cal)
    assert out["model_edge_enabled"] is True
    model_cands = [
        c for c in out["candidates"] if c["strategy_id"] == "MODEL_PROBABILITY_EDGE"
    ]
    assert len(model_cands) == 1
    assert model_cands[0]["authority"] == "SHADOW_ONLY"
    assert model_cands[0]["capital_authority"] is False
    assert "MODEL_PROBABILITY_EDGE" in (out.get("provenance") or {}).get(
        "strategy_ids", []
    )


def test_competition_multi_merges_ingested_events():
    a = _ingest()
    a["run_id"] = "R-MULTI"
    a["event_id"] = "E-A"
    a["markets"][0]["market_id"] = "M-A"
    b = _ingest()
    b["run_id"] = "R-MULTI:E-B"
    b["event_id"] = "E-B"
    b["markets"][0]["market_id"] = "M-B"
    skipped = {"status": "REJECTED", "run_id": "R-MULTI", "event_id": "E-SKIP"}

    out = run_strategy_competition_multi([a, skipped, b], run_id="R-MULTI")
    assert out["status"] == "COMPUTED"
    assert out["competed_event_count"] == 2
    assert out["ingest_count"] == 3
    assert out["event_id"] == "MULTI"
    assert out["capital_authority"] is False
    assert out["execution_authority"] is False
    assert set(out["provenance"]["event_ids"]) == {"E-A", "E-B"}
    assert out["candidate_count"] >= 2
    event_ids = {c["event_id"] for c in out["candidates"]}
    assert "E-A" in event_ids and "E-B" in event_ids
    assert all(c.get("provenance", {}).get("multi_event_compete") for c in out["candidates"])
    # Sorted by descending score
    scores = [float(c.get("score") or 0.0) for c in out["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_competition_multi_fail_closed_without_ingested():
    out = run_strategy_competition_multi(
        [{"status": "REJECTED", "run_id": "R0"}, {"status": "NOT_COMPUTABLE"}],
        run_id="R0",
    )
    assert out["status"] == "NOT_COMPUTABLE"
    assert out["competed_event_count"] == 0
    assert out["candidate_count"] == 0
    assert out["capital_authority"] is False
