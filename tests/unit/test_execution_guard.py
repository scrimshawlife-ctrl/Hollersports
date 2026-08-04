from hollersports.runes.execution_guard import run_execution_guard


def test_approves_paper_only():
    packet = run_execution_guard(
        {
            "strategy_id": "MARKET_CONSENSUS_EDGE",
            "event_id": "E1",
            "market_id": "M1",
            "selection": "HOME_ML",
            "score": 0.8,
            "packet_refs": {"x": "1"},
        },
        {
            "run_id": "R1",
            "price": 1.91,
            "bankroll": 1000.0,
            "human_max_stake": 25.0,
            "gates": {
                "source_health_gate": True,
                "governance_gate": True,
                "truth_gate": True,
                "liquidity_gate": True,
                "bankroll_gate": True,
            },
        },
    )
    assert packet["status"] == "APPROVED_FOR_PAPER"
    assert packet["mode"] == "PAPER_ONLY"
    assert packet["authority"] == "SHADOW_FIRST"
    assert packet["capital_authority"] is False
    assert packet["execution_authority"] is False
    assert packet["stake"] > 0
    assert packet["stake"] <= 25.0


def test_failed_gate_rejects():
    packet = run_execution_guard(
        {
            "strategy_id": "X",
            "event_id": "E",
            "market_id": "M",
            "selection": "S",
            "score": 0.5,
            "packet_refs": {},
        },
        {
            "run_id": "R1",
            "price": 1.91,
            "bankroll": 1000,
            "human_max_stake": 25,
            "gates": {
                "source_health_gate": False,
                "governance_gate": True,
                "truth_gate": True,
                "liquidity_gate": True,
                "bankroll_gate": True,
            },
        },
    )
    assert packet["status"] == "REJECTED"
