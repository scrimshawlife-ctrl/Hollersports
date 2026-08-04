from hollersports.runes.settlement_engine import settle_entry


def test_settle_win():
    s = settle_entry(
        {"entry_id": "1", "selection": "HOME_ML", "stake": 10.0, "price": 1.91},
        {"result": "WIN", "source": "FIXTURE", "final_score": "110-100"},
    )
    assert s["status"] == "WIN"
    assert s["authority"] == "SHADOW_ONLY"
    assert "source" in s["provenance"]


def test_settle_pending_without_result():
    s = settle_entry(
        {"entry_id": "1", "selection": "HOME_ML", "stake": 10.0, "price": 1.91},
        None,
    )
    assert s["status"] == "PENDING"
