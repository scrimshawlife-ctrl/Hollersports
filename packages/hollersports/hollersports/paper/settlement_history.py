"""Cumulative append-only settlement history for advice calibration.

Stores settled paper outcomes across operator days so calibration can grow
sample size. Simulation metrics only — never real money.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.schemas.hashing import packet_hash, stable_json

GENESIS_PREV_HASH = ""
_SETTLED = frozenset({"WIN", "LOSS", "PUSH", "VOID"})


def settlement_history_path(data_root: Path | str) -> Path:
    """Default path: ``{data_root}/ledgers/settlements_history.jsonl``."""
    root = Path(data_root)
    path = root / "ledgers" / "settlements_history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_settlement_history(
    ledger_path: Path | str | None = None,
    *,
    data_root: Path | str | None = None,
    limit: int | None = None,
    settled_only: bool = True,
) -> list[dict[str, Any]]:
    """Read cumulative settlement rows (oldest-first). Missing file → []."""
    if ledger_path is None:
        if data_root is None:
            return []
        path = settlement_history_path(data_root)
    else:
        path = Path(ledger_path)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            continue
        if settled_only and str(row.get("status") or "").upper() not in _SETTLED:
            continue
        rows.append(row)
    if limit is not None and limit >= 0:
        rows = rows[-limit:] if limit else []
    return rows


def _last_entry_hash(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return GENESIS_PREV_HASH
    return str(rows[-1].get("entry_hash") or GENESIS_PREV_HASH)


def append_settlement_history(
    data_root: Path | str,
    entries: Sequence[Mapping[str, Any]] | None,
    *,
    run_id: str = "UNKNOWN",
    fixture: str | None = None,
    recorded_at: str | None = None,
) -> list[dict[str, Any]]:
    """Append settlement entries to the cumulative calibration bank.

    Each row is hash-chained. Forces capital/execution authority false.
    Returns list of written records.
    """
    path = settlement_history_path(data_root)
    # Read full chain including PENDING for hash continuity.
    all_rows: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                all_rows.append(json.loads(line))

    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    written: list[dict[str, Any]] = []
    for raw in entries or []:
        if not isinstance(raw, Mapping):
            continue
        payload: dict[str, Any] = {
            "status": str(raw.get("status") or "").upper(),
            "entry_id": str(raw.get("entry_id") or ""),
            "run_id": str(raw.get("run_id") or run_id),
            "event_id": str(raw.get("event_id") or ""),
            "market_id": str(raw.get("market_id") or ""),
            "selection": str(raw.get("selection") or ""),
            "strategy_id": str(
                raw.get("strategy_id")
                or (raw.get("provenance") or {}).get("strategy_id")
                or "UNKNOWN"
            ),
            "league": str(raw.get("league") or "UNKNOWN"),
            "market_type": str(raw.get("market_type") or "UNKNOWN"),
            "stake": float(raw.get("stake") or raw.get("paper_stake") or 0.0),
            "pnl": float(raw.get("pnl") or raw.get("settled_value") or 0.0),
            "price": float(raw.get("price") or 0.0),
            "fixture": fixture or "",
            "recorded_at": recorded_at,
            "capital_authority": False,
            "execution_authority": False,
            "mode": "PAPER_ONLY",
        }
        prev_hash = _last_entry_hash(all_rows)
        entry_hash = packet_hash({"payload": payload, "prev_hash": prev_hash})
        record = {**payload, "prev_hash": prev_hash, "entry_hash": entry_hash}
        all_rows.append(record)
        written.append(record)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(stable_json(record) + "\n")

    return written


def calibration_entries_for_store(
    data_root: Path | str,
    last_batch: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Prefer cumulative history; fall back to last settlement batch."""
    hist = read_settlement_history(data_root=data_root, settled_only=True)
    if hist:
        return hist
    return [
        dict(e)
        for e in (last_batch or [])
        if isinstance(e, Mapping)
        and str(e.get("status") or "").upper() in _SETTLED
    ]
