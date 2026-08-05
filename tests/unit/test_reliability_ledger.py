"""Append-only reliability history ledger."""

from hollersports.paper.reliability_ledger import (
    GENESIS_PREV_HASH,
    append_reliability_snapshot,
    read_reliability_history,
    record_reliability_from_settlements,
    reliability_ledger_path,
)


def _sample_packet(sample_size: int = 2) -> dict:
    return {
        "schema_version": "ReliabilityBucketPacket.v1",
        "status": "COMPUTED" if sample_size else "EMPTY",
        "sample_size": sample_size,
        "bucket_count": 1 if sample_size else 0,
        "buckets": (
            [
                {
                    "dimension": "strategy_id",
                    "key": "MARKET_CONSENSUS_EDGE",
                    "sample_size": sample_size,
                    "hit_rate": 0.5,
                    "sim_roi": 0.1,
                    "note": "simulation_metrics_only",
                }
            ]
            if sample_size
            else []
        ),
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
    }


def test_missing_file_empty(tmp_path):
    path = reliability_ledger_path(tmp_path)
    assert read_reliability_history(path) == []
    assert not path.is_file() or path.read_text() == ""


def test_append_chain_from_genesis(tmp_path):
    path = reliability_ledger_path(tmp_path)
    r1 = append_reliability_snapshot(
        path, _sample_packet(2), recorded_at="2026-08-04T12:00:00Z"
    )
    assert r1["prev_hash"] == GENESIS_PREV_HASH
    assert r1["entry_hash"]
    assert r1["capital_authority"] is False
    assert r1["execution_authority"] is False
    assert r1["recorded_at"] == "2026-08-04T12:00:00Z"

    r2 = append_reliability_snapshot(
        path, _sample_packet(3), recorded_at="2026-08-04T13:00:00Z"
    )
    assert r2["prev_hash"] == r1["entry_hash"]
    assert r2["entry_hash"] != r1["entry_hash"]

    rows = read_reliability_history(path)
    assert len(rows) == 2
    assert rows[0]["entry_hash"] == r1["entry_hash"]
    assert rows[1]["prev_hash"] == r1["entry_hash"]


def test_read_limit_last_n(tmp_path):
    path = reliability_ledger_path(tmp_path)
    for i in range(5):
        append_reliability_snapshot(
            path,
            _sample_packet(i + 1),
            recorded_at=f"2026-08-04T1{i}:00:00Z",
        )
    last = read_reliability_history(path, limit=1)
    assert len(last) == 1
    assert last[0]["sample_size"] == 5

    last3 = read_reliability_history(path, limit=3)
    assert len(last3) == 3
    assert [r["sample_size"] for r in last3] == [3, 4, 5]


def test_record_from_settlements(tmp_path):
    entries = [
        {
            "status": "WIN",
            "strategy_id": "MARKET_CONSENSUS_EDGE",
            "league": "NBA",
            "market_type": "ML",
            "stake": 10.0,
            "pnl": 9.0,
        },
        {
            "status": "LOSS",
            "strategy_id": "MARKET_CONSENSUS_EDGE",
            "league": "NBA",
            "market_type": "ML",
            "stake": 10.0,
            "pnl": -10.0,
        },
    ]
    rec = record_reliability_from_settlements(tmp_path, entries)
    assert rec["schema_version"] == "ReliabilityBucketPacket.v1"
    assert rec["sample_size"] == 2
    assert rec["entry_hash"]
    hist = read_reliability_history(reliability_ledger_path(tmp_path))
    assert len(hist) == 1
