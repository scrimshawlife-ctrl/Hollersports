from hollersports.pipelines.strategy_competition import run_strategy_competition

def _ingest():
    return {
        "schema_version": "MarketIngestionPacket.v1",
        "status": "INGESTED",
        "run_id": "R1",
        "event_id": "E1",
        "markets": [
            {
                "market_id": "M1",
                "selection": "HOME_ML",
                "consensus_score": 0.8,
                "public_bet_pct": 0.75,
                "handle_pct": 0.5,
                "fade_selection": "AWAY_ML",
                "clv_retention": 0.02,
            }
        ],
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
