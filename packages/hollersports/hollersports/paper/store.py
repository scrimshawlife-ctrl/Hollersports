"""Local paper ledger store paths (cwd-relative defaults)."""

from __future__ import annotations

from pathlib import Path

DEFAULT_LEDGER_ROOT = Path("data/ledgers")
DEFAULT_LEDGER_NAME = "paper.jsonl"


def ledger_root(root: Path | str | None = None) -> Path:
    """Return ledger root directory, creating parents if needed."""
    path = Path(root) if root is not None else DEFAULT_LEDGER_ROOT
    path.mkdir(parents=True, exist_ok=True)
    return path


def ledger_path(
    name: str = DEFAULT_LEDGER_NAME,
    *,
    root: Path | str | None = None,
) -> Path:
    """Resolve a ledger file path under the store root (creates parents)."""
    return ledger_root(root) / name
