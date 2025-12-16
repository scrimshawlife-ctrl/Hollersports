"""
Strongly-typed data models for Contextual Correction Maps (CCM)

All models are frozen dataclasses to ensure immutability and thread-safety.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from datetime import datetime


class PropMarket(str, Enum):
    """Supported prop markets"""
    PTS = "PTS"
    REB = "REB"
    AST = "AST"
    PRA = "PRA"
    PR = "PR"
    PA = "PA"
    RA = "RA"
    BLK = "BLK"
    STL = "STL"
    TO = "TO"
    FG3M = "FG3M"
    MIN = "MIN"


class PropSide(str, Enum):
    """Prop bet side"""
    HIGHER = "higher"
    LOWER = "lower"


@dataclass(frozen=True)
class PropRecord:
    """
    Historical prop outcome record.

    Represents a single prop bet with its line, actual result, and metadata.
    """
    # Core identifiers
    player_id: str
    game_id: str
    market: PropMarket
    line: float
    actual: float
    side: PropSide
    timestamp: str  # ISO 8601

    # Team/opponent context
    team_id: str
    opp_id: str
    venue_id: str

    # Optional fields
    hit: Optional[bool] = None  # Computed if missing
    model_projection: Optional[float] = None
    minutes_expected: Optional[float] = None

    def compute_hit(self) -> bool:
        """Compute whether the pick was correct based on side."""
        if self.side == PropSide.HIGHER:
            return self.actual > self.line
        else:  # LOWER
            return self.actual < self.line

    def compute_residual(self) -> float:
        """Compute residual: actual - line."""
        return self.actual - self.line


@dataclass(frozen=True)
class GameContext:
    """
    Contextual features for a game that may affect prop outcomes.

    Includes venue, travel, coaching, and matchup information.
    """
    # Required
    venue_id: str
    is_home: bool
    team_id: str
    opp_id: str

    # Travel context
    travel_b2b: Optional[bool] = None
    travel_distance_km: Optional[float] = None
    timezone_delta: Optional[int] = None
    rest_days: Optional[int] = None

    # Coaching/rotation context
    coach_id: Optional[str] = None
    rotation_depth_proxy: Optional[float] = None

    # Matchup context
    pace_proxy: Optional[float] = None
    opponent_defense_proxy: Optional[float] = None
    scheme_proxy: Optional[str] = None


@dataclass(frozen=True)
class Provenance:
    """
    Provenance metadata for reproducibility and auditing.

    Every CCM artifact includes provenance to ensure deterministic builds.
    """
    run_id: str
    created_at: str  # ISO 8601
    seed: int
    inputs_hash: str
    config_hash: str
    schema_version: str = "1.0.0"
    git_sha: Optional[str] = None


@dataclass(frozen=True)
class CorrectionEntry:
    """
    A single correction entry in the CCM.

    Represents the learned adjustment for a specific context regime.
    """
    # Context key
    market: PropMarket
    venue_bucket: int
    coach_bucket: int
    is_home: int
    travel_b2b: int
    timezone_bucket: int

    # Correction statistics
    mean_delta: float
    median_delta: float
    count: int
    confidence: float
    dispersion: float

    def key_tuple(self) -> tuple:
        """Return hashable key for lookups."""
        return (
            self.market.value,
            self.venue_bucket,
            self.coach_bucket,
            self.is_home,
            self.travel_b2b,
            self.timezone_bucket,
        )


@dataclass(frozen=True)
class CorrectionMap:
    """
    Complete Contextual Correction Map with all entries and metadata.

    This is the artifact persisted to correction_maps.json and loaded at runtime.
    """
    provenance: Provenance
    config: dict
    corrections: list[CorrectionEntry]

    def __post_init__(self):
        """Build internal lookup index after initialization."""
        # Since this is frozen, we can't set attributes directly
        # Use object.__setattr__ for post-init setup
        lookup = {}
        for entry in self.corrections:
            lookup[entry.key_tuple()] = entry
        object.__setattr__(self, '_lookup', lookup)

    def get_correction(self, key: tuple) -> Optional[CorrectionEntry]:
        """Fast lookup of correction by key tuple."""
        return getattr(self, '_lookup', {}).get(key)

    def __len__(self) -> int:
        """Return number of correction entries."""
        return len(self.corrections)
