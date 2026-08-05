from hollersports.runes.reliability_bucket import compute_reliability_buckets


def test_reliability_empty():
    p = compute_reliability_buckets([])
    assert p["status"] == "EMPTY"
    assert p["bucket_count"] == 0
    assert p["capital_authority"] is False
    assert p["mode"] == "ADVISORY_ONLY"


def test_reliability_by_strategy():
    entries = [
        {"status": "WIN", "strategy_id": "A", "league": "NBA", "market_type": "MONEYLINE", "stake": 10, "pnl": 9},
        {"status": "LOSS", "strategy_id": "A", "league": "NBA", "market_type": "MONEYLINE", "stake": 10, "pnl": -10},
        {"status": "WIN", "strategy_id": "B", "league": "NFL", "market_type": "SPREAD", "stake": 10, "pnl": 9},
        {"status": "PENDING", "strategy_id": "A", "league": "NBA", "market_type": "MONEYLINE", "stake": 10, "pnl": 0},
    ]
    p = compute_reliability_buckets(entries)
    assert p["sample_size"] == 3  # PENDING excluded
    by_strategy = [b for b in p["buckets"] if b["dimension"] == "strategy_id"]
    a = next(b for b in by_strategy if b["key"] == "A")
    assert a["sample_size"] == 2
    assert a["hit_rate"] == 0.5
    assert a["note"] == "simulation_metrics_only"
