from __future__ import annotations
from typing import Any


def not_computable(schema_version: str, reason: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": schema_version,
        "status": "NOT_COMPUTABLE",
        "authority": "SHADOW_ONLY",
        "reason": reason,
        "capital_authority": False,
        "execution_authority": False,
        "provenance": {},
    }
    out.update(extra)
    return out
