"""Append-only hash-chained reliability snapshot ledger (JSONL).

Advice-quality history only — never money or execution authority.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from hollersports.schemas.hashing import packet_hash, stable_json

GENESIS_PREV_HASH = ""


def reliability_ledger_path(data_root: Path | str) -> Path:
    """Default path: ``{data_root}/ledgers/reliability.jsonl``."""
    root = Path(data_root)
    path = root / "ledgers" / "reliability.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_reliability_history(
    ledger_path: Path | str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read reliability history rows. Missing file → [].

    Rows are oldest-first. When ``limit`` is set, return the last N rows
    (still oldest-first within the window).
    """
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
    if limit is not None and limit >= 0:
        rows = rows[-limit:] if limit else []
    return rows


def _last_entry_hash(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return GENESIS_PREV_HASH
    last = rows[-1]
    return str(last.get("entry_hash") or GENESIS_PREV_HASH)


def append_reliability_snapshot(
    ledger_path: Path | str,
    packet: Mapping[str, Any] | dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Append a reliability bucket packet snapshot with hash chain linkage.

    entry_hash = sha256(stable_json({payload, prev_hash}))
    Forces capital_authority and execution_authority false.
    """
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = read_reliability_history(path)
    prev_hash = _last_entry_hash(rows)

    payload: dict[str, Any] = dict(packet)
    payload.pop("prev_hash", None)
    payload.pop("entry_hash", None)
    payload["capital_authority"] = False
    payload["execution_authority"] = False
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload["recorded_at"] = recorded_at

    entry_hash = packet_hash({"payload": payload, "prev_hash": prev_hash})

    record: dict[str, Any] = {
        **payload,
        "prev_hash": prev_hash,
        "entry_hash": entry_hash,
    }

    line = stable_json(record) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)

    return record


def record_reliability_from_settlements(
    data_root: Path | str,
    settled_entries: list[Mapping[str, Any]] | list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Compute reliability buckets and append a history snapshot.

    Returns the appended ledger record (or the empty-status packet record).
    """
    from hollersports.runes.reliability_bucket import compute_reliability_buckets

    packet = compute_reliability_buckets(settled_entries or [])
    path = reliability_ledger_path(data_root)
    return append_reliability_snapshot(path, packet)
