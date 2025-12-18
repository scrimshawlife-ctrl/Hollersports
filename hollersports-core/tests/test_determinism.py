from __future__ import annotations
from hollersports_core.util.hashing import stable_json_dumps, sha256_hex


def test_stable_json_and_hash_deterministic():
    obj = {"b": 2, "a": 1}
    s1 = stable_json_dumps(obj)
    s2 = stable_json_dumps({"a": 1, "b": 2})
    assert s1 == s2
    assert sha256_hex(s1) == sha256_hex(s2)
