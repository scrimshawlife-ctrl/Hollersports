"""Multi-poll market feature sequences (G0 plumbing).

Append-only JSONL of polls; load ordered feature vectors per line key for
temporal models. Never invents odds — only stores what was observed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.ml.features import FEATURE_NAMES, extract_feature_vector, vector_list
from hollersports.schemas.hashing import packet_hash


def sequence_store_path(data_root: Path | str) -> Path:
    return Path(data_root) / "ml" / "market_sequences.jsonl"


def _line_key(market: Mapping[str, Any]) -> str:
    eid = str(market.get("event_id") or "")
    mtype = str(market.get("market_type") or "")
    sel = str(market.get("selection") or "")
    point = market.get("point")
    return f"{eid}|{mtype}|{sel}|{point}"


def append_poll(
    data_root: Path | str,
    markets: Sequence[Mapping[str, Any]],
    *,
    poll_id: str | None = None,
    fetched_at: float | None = None,
) -> dict[str, Any]:
    """Append one poll of markets as feature rows. Fail soft on unusable rows."""
    path = sequence_store_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = float(fetched_at if fetched_at is not None else time.time())
    pid = poll_id or f"poll-{int(ts)}"
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for m in markets:
            if not isinstance(m, Mapping):
                continue
            feat = extract_feature_vector(m)
            if feat is None:
                continue
            rec = {
                "poll_id": pid,
                "fetched_at": ts,
                "line_key": _line_key(m),
                "event_id": str(m.get("event_id") or ""),
                "market_id": str(m.get("market_id") or ""),
                "selection": str(m.get("selection") or ""),
                "x": vector_list(feat),
                "features": feat,
                "price": m.get("price"),
                "label": m.get("result") or m.get("y"),
            }
            f.write(json.dumps(rec, sort_keys=True) + "\n")
            n += 1
    return {
        "schema_version": "HollerSequencePoll.v1",
        "status": "RECORDED" if n else "EMPTY",
        "poll_id": pid,
        "rows_written": n,
        "path": str(path),
        "capital_authority": False,
        "execution_authority": False,
    }


def load_polls(data_root: Path | str) -> list[dict[str, Any]]:
    path = sequence_store_path(data_root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def sequences_by_line_key(
    data_root: Path | str,
    *,
    min_len: int = 2,
    max_len: int = 64,
) -> dict[str, list[list[float]]]:
    """Ordered feature sequences per line_key (by fetched_at ascending)."""
    rows = load_polls(data_root)
    rows.sort(key=lambda r: (str(r.get("line_key")), float(r.get("fetched_at") or 0)))
    buckets: dict[str, list[list[float]]] = {}
    for r in rows:
        key = str(r.get("line_key") or "")
        x = r.get("x")
        if not key or not isinstance(x, list):
            continue
        try:
            vec = [float(v) for v in x]
        except (TypeError, ValueError):
            continue
        buckets.setdefault(key, []).append(vec)
    # trim
    out: dict[str, list[list[float]]] = {}
    for k, seq in buckets.items():
        if len(seq) < min_len:
            continue
        out[k] = seq[-max_len:]
    return out


def load_fixture_sequences(path: Path | str) -> list[dict[str, Any]]:
    """Load fixture sequence file: {sequences:[{line_key, x_seq, y?}, ...]}.

    ``x_seq`` is list of feature rows (each length = n_features).
    """
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict):
        seqs = raw.get("sequences") or raw.get("items") or []
        return [r for r in seqs if isinstance(r, dict)]
    return []


def write_fixture_sequences(
    path: Path | str,
    sequences: Sequence[Mapping[str, Any]],
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "schema_version": "HollerFixtureSequences.v1",
        "feature_names": list(FEATURE_NAMES),
        "sequences": [dict(s) for s in sequences],
        "capital_authority": False,
        "execution_authority": False,
    }
    body["packet_hash"] = packet_hash(
        {"n": len(sequences), "feature_names": list(FEATURE_NAMES)}
    )
    out.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
