from pathlib import Path

from hollersports.paper.ledger import append_paper_entry, read_ledger


def test_append_only_hash_chain(tmp_path: Path):
    path = tmp_path / "paper.jsonl"
    e1 = append_paper_entry(path, {"entry_id": "1", "stake": 10.0})
    e2 = append_paper_entry(path, {"entry_id": "2", "stake": 5.0})
    rows = read_ledger(path)
    assert len(rows) == 2
    assert rows[1]["prev_hash"] == rows[0]["entry_hash"]
    assert e1["capital_authority"] is False
