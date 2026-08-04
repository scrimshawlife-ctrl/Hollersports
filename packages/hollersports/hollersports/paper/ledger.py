"""Append-only hash-chained paper ledger (JSONL)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from hollersports.schemas.hashing import packet_hash, stable_json

# First entry chains from this sentinel prev_hash.
GENESIS_PREV_HASH = ""


def read_ledger(ledger_path: Path | str) -> list[dict[str, Any]]:
    """Read all JSONL rows from a paper ledger. Missing file → empty list."""
    path = Path(ledger_path)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _last_entry_hash(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return GENESIS_PREV_HASH
    last = rows[-1]
    return str(last.get("entry_hash") or GENESIS_PREV_HASH)


def append_paper_entry(
    ledger_path: Path | str,
    entry: Mapping[str, Any] | dict[str, Any],
) -> dict[str, Any]:
    """Append a paper ledger entry with hash chain linkage.

    entry_hash = sha256(stable_json({payload, prev_hash}))
    Always forces capital_authority and execution_authority false.
    Creates parent directories as needed.
    """
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = read_ledger(path)
    prev_hash = _last_entry_hash(rows)

    # Payload is entry fields only (no chain metadata).
    payload: dict[str, Any] = dict(entry)
    payload.pop("prev_hash", None)
    payload.pop("entry_hash", None)
    payload["capital_authority"] = False
    payload["execution_authority"] = False

    entry_hash = packet_hash({"payload": payload, "prev_hash": prev_hash})

    record: dict[str, Any] = {
        **payload,
        "prev_hash": prev_hash,
        "entry_hash": entry_hash,
    }

    # Append as single JSONL line using stable key order for readability.
    line = stable_json(record) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)

    return record
