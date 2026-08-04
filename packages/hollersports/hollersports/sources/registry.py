"""Load and query sources/registry.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DEFAULT_REGISTRY = Path(__file__).with_name("registry.yaml")


def load_registry(path: Path | str | None = None) -> dict[str, Any]:
    """Load the source registry YAML. Defaults to package-local registry.yaml."""
    reg_path = Path(path) if path is not None else _DEFAULT_REGISTRY
    with open(reg_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return {"sources": []}
    data.setdefault("sources", [])
    return data


def list_sources(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    reg = registry if registry is not None else load_registry()
    sources = reg.get("sources") or []
    return [s for s in sources if isinstance(s, dict)]


def get_source(
    source_id: str, registry: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    for source in list_sources(registry):
        if source.get("id") == source_id:
            return source
    return None
