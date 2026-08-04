"""JSON Schema validation for HollerSports packet dicts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonschema


def _repo_root_candidates() -> list[Path]:
    """Resolve likely repo roots so tests and runtime can find schemas/json."""
    candidates: list[Path] = []
    env_root = os.environ.get("HOLLERSPORTS_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    candidates.append(Path.cwd())
    # packages/hollersports/hollersports/schemas/validate.py -> repo root is parents[4]
    here = Path(__file__).resolve()
    if len(here.parents) >= 5:
        candidates.append(here.parents[4])
    return candidates


def schema_path(name: str) -> Path:
    """Return path to `{name}.schema.json` under schemas/json/."""
    filename = f"{name}.schema.json"
    for root in _repo_root_candidates():
        path = root / "schemas" / "json" / filename
        if path.is_file():
            return path
    # Prefer cwd for the error message (matches brief / test invocation)
    return Path.cwd() / "schemas" / "json" / filename


def validate_packet(packet: dict[str, Any], schema_name: str) -> dict[str, Any]:
    """Validate packet against schemas/json/{schema_name}.schema.json.

    Returns the packet unchanged on success; raises jsonschema.ValidationError
    (or FileNotFoundError if the schema file is missing).
    """
    path = schema_path(schema_name)
    with open(path, encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(packet, schema)
    return packet
