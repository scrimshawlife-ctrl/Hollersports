"""
Core ABX-Core v1.2 compliance layer for HollerSports.

Enforces:
- SEED: deterministic behavior, provenance tracking
- Config-driven operation (no magic numbers)
- Modular, composable architecture
"""

from hollersports.core.config import Settings, get_settings
from hollersports.core.models import (
    MatchupContext,
    PlayerProjection,
    PlayerStats,
    TeamContext,
)

__all__ = [
    "Settings",
    "get_settings",
    "MatchupContext",
    "PlayerProjection",
    "PlayerStats",
    "TeamContext",
]
