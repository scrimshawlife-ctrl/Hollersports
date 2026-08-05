from hollersports.runes.performance_tracker import compute_performance
from hollersports.runes.promotion_evaluator import evaluate_promotion


def test_performance_excludes_pending():
    perf = compute_performance([
        {"status": "WIN", "stake": 10, "pnl": 9.1},
        {"status": "PENDING", "stake": 10, "pnl": 0},
        {"status": "LOSS", "stake": 10, "pnl": -10},
    ])
    assert perf["sample_size"] == 2
    assert perf["authority"] == "SHADOW_ONLY"


def test_promotion_blocked_small_sample():
    prom = evaluate_promotion(
        {"sample_size": 2, "roi": 0.1, "max_drawdown": 0.05, "clv_retention": 0.0},
        {
            "source_health_pass_rate": 1.0,
            "invariance_pass": True,
            "regimes": 1,
            "market_types": 1,
            "unresolved_blockers": 0,
        },
    )
    assert prom["status"] == "BLOCKED"
    assert "sample_size" in str(prom["failed_gates"]).lower() or any(
        "sample" in g.lower() for g in prom["failed_gates"]
    )
