from hollersports.strategies.registry import load_strategies, registry_packet

def test_registry_three_market_strategies_by_default():
    ids = sorted(s.strategy_id for s in load_strategies())
    assert ids == [
        "CLV_RETENTION_EDGE",
        "MARKET_CONSENSUS_EDGE",
        "PUBLIC_OVERREACTION_FADE",
    ]
    assert registry_packet()["authority"] == "SHADOW_ONLY"

def test_model_edge_not_loaded_without_gate():
    ids = [s.strategy_id for s in load_strategies(allow_model_edge=False)]
    assert "MODEL_PROBABILITY_EDGE" not in ids
