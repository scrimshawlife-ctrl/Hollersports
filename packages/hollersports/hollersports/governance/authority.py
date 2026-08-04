from __future__ import annotations
from enum import Enum
from typing import Any, Mapping


class Authority(str, Enum):
    SHADOW_ONLY = "SHADOW_ONLY"
    FORECAST_SUPPORT = "FORECAST_SUPPORT"
    SHADOW_FIRST = "SHADOW_FIRST"
    PROJECTION_ONLY = "PROJECTION_ONLY"
    NOT_COMPUTABLE = "NOT_COMPUTABLE"


def assert_no_live_capital(packet: Mapping[str, Any]) -> None:
    if packet.get("capital_authority") is True:
        raise ValueError("capital_authority must be false in v1")
    if packet.get("execution_authority") is True:
        raise ValueError("execution_authority must be false in v1")
    if packet.get("mode") == "LIVE_APPROVED":
        raise ValueError("LIVE_APPROVED mode forbidden in v1")
