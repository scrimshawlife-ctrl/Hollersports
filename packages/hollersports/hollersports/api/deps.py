"""API dependencies: data root resolution and last-run state store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hollersports.governance.authority import assert_no_live_capital

# Packet keys persisted under data_root/runs/
_STATE_KEYS = (
    "ingest",
    "ingests",
    "competition",
    "paper",
    "settlements",
    "performance",
    "promotion",
    "dashboard",
    "fixture",
    "meta",
    "calibration",
    "ml_train",
    "ml_ensemble",
    "ml_annotate",
    "ml_retrain",
    "ml_axial",
    "ml_retrain_apply",
    "ml_axial_train",
    "ml_rss_sentiment",
)


def resolve_data_root(data_root: str | Path | None = None) -> Path:
    """Resolve data root: explicit arg → HOLLER_DATA_ROOT → ./data."""
    if data_root is not None:
        root = Path(data_root)
    else:
        env = os.environ.get("HOLLER_DATA_ROOT")
        root = Path(env) if env else Path("data")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve_fixture_dir(fixture: str) -> Path:
    """Locate a named fixture day directory (e.g. day001).

    Search order:
      1. fixtures/<name> under cwd
      2. repo-root/fixtures/<name> (walk parents looking for fixtures/)
      3. absolute/relative path if fixture already points at a directory
    """
    name = str(fixture or "").strip()
    if not name:
        raise FileNotFoundError("fixture name is required")

    candidate = Path(name)
    if candidate.is_dir() and (candidate / "meta.json").is_file():
        return candidate.resolve()

    cwd_hit = Path("fixtures") / name
    if cwd_hit.is_dir() and (cwd_hit / "meta.json").is_file():
        return cwd_hit.resolve()

    # Walk up from this package and cwd for fixtures/<name>
    search_roots = [Path.cwd(), *Path.cwd().parents]
    here = Path(__file__).resolve()
    search_roots.extend([here.parent, *here.parents])
    seen: set[Path] = set()
    for base in search_roots:
        if base in seen:
            continue
        seen.add(base)
        hit = base / "fixtures" / name
        if hit.is_dir() and (hit / "meta.json").is_file():
            return hit.resolve()

    raise FileNotFoundError(f"fixture not found: {name}")


class RunStore:
    """In-memory + disk last-run state under ``data_root/runs``."""

    def __init__(self, data_root: str | Path | None = None) -> None:
        self.data_root = resolve_data_root(data_root)
        self.runs_dir = self.data_root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.ledgers_dir = self.data_root / "ledgers"
        self.ledgers_dir.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, Any] = {}
        self._load()

    def _state_path(self) -> Path:
        return self.runs_dir / "last_run.json"

    def _load(self) -> None:
        path = self._state_path()
        if not path.is_file():
            self._state = {}
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            self._state = raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            self._state = {}

    def _persist(self) -> None:
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, sort_keys=True, default=str)

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        return dict(self._state)

    def put(self, key: str, value: Any) -> None:
        if isinstance(value, dict):
            assert_no_live_capital(value)
            if value.get("mode") == "LIVE_APPROVED":
                raise ValueError("LIVE_APPROVED mode forbidden in v1")
        self._state[key] = value
        self._persist()

    def update(self, **packets: Any) -> None:
        for key, value in packets.items():
            if key not in _STATE_KEYS and key not in self._state:
                # Allow known + dynamic keys; still enforce authority on packets.
                pass
            if isinstance(value, dict):
                assert_no_live_capital(value)
                if value.get("mode") == "LIVE_APPROVED":
                    raise ValueError("LIVE_APPROVED mode forbidden in v1")
            self._state[key] = value
        self._persist()

    def ledger_path(self, portfolio_id: str = "default") -> Path:
        path = self.ledgers_dir / f"{portfolio_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
