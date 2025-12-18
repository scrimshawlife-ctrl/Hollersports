from __future__ import annotations
import json
from pathlib import Path
from hollersports_core.util.io import append_line
from hollersports_core.util.hashing import stable_json_dumps


def test_append_only_semantics(tmp_path: Path):
    p = tmp_path / "ledger.jsonl"
    append_line(p, stable_json_dumps({"n": 1}))
    append_line(p, stable_json_dumps({"n": 2}))
    lines = p.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["n"] == 1
    assert json.loads(lines[1])["n"] == 2
