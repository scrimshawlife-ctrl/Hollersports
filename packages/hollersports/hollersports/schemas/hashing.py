from __future__ import annotations
import hashlib
import json
from typing import Any


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def packet_hash(obj: dict) -> str:
    return hashlib.sha256(stable_json(obj).encode("utf-8")).hexdigest()
