"""
Type definitions for NHL SOG prop engine.

Strongly-typed, immutable data structures for deterministic processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict


class Side(str, Enum):
    """Prop bet side"""
    HIGHER = "HIGHER"
    LOWER = "LOWER"


@dataclass(frozen=True)
class NHLGameRow:
    """
    Single player-game observation from input dataset.

    Represents one player's performance in one game with context.
    """
    # Game identifiers
    game_id: str
    date: str  # YYYY-MM-DD
    team: str
    opponent: str
    is_home: int  # 0 or 1

    # Player identifiers
    player_id: str
    player_name: str
    position: str  # F, D, G

    # Performance stats
    toi_minutes: float
    sog: int  # shots on goal (actual)

    # Optional context
    pp_toi_minutes: Optional[float] = None
    line_sog: Optional[float] = None  # Prop line (for backtest)

    # Team/opponent context (optional)
    team_pace_proxy: Optional[float] = None
    opponent_shot_suppression_proxy: Optional[float] = None


@dataclass(frozen=True)
class SOGProp:
    """
    A shots-on-goal prop bet specification.
    """
    player_id: str
    player_name: str
    line: float
    side: Side
    game_id: Optional[str] = None


@dataclass(frozen=True)
class SOGProjection:
    """
    Complete SOG projection with statistics and provenance.

    Includes median-floor estimates, probability, confidence, and reasons.
    """
    player_id: str
    player_name: str
    game_id: str

    # Core statistics
    mu: float  # Mean projection
    sigma: float  # Standard deviation
    median: float  # Median estimate
    floor: float  # Conservative floor (25th percentile)

    # Probability & confidence
    p_hit: float  # Monte Carlo hit probability
    confidence: float  # Overall confidence score (0-1)

    # Context
    line: float  # Prop line being evaluated
    side: Side  # Higher or lower

    # Explanation
    reasons: List[str]  # Human-readable reasons
    flags: List[str]  # Warning flags

    # Provenance
    provenance_hash: str

    # Additional metrics
    role_score: float = 0.0  # Role stability score
    opponent_modifier: float = 0.0  # Opponent adjustment
    survivability_score: float = 0.0  # From AAL-core normalizer


@dataclass(frozen=True)
class SlatePickResult:
    """
    Result of picker algorithm on a slate.

    Contains ranked legs and various slate configurations.
    """
    # Top picks
    ultra_safe_3leg: List[SOGProjection]
    ultra_safe_5leg: List[SOGProjection]

    # Alternative configurations
    correlated_5leg: Optional[List[SOGProjection]] = None
    balanced_5leg: Optional[List[SOGProjection]] = None

    # Metadata
    total_candidates: int = 0
    filtered_candidates: int = 0
    provenance_hash: str = ""


@dataclass
class FeatureSet:
    """
    Computed features for a player-game.

    Mutable for intermediate computation, then frozen in projection.
    """
    player_id: str
    game_id: str

    # Historical features
    last5_sog_weighted: float
    season_sog_median: float
    last10_sog_list: List[int]  # For volatility check

    # Role features
    toi_last5_median: float
    toi_season_median: float
    pp_share: Optional[float] = None
    pp_share_last5: Optional[float] = None

    # Context features
    opponent_pos_sog_allowed: float = 0.0
    is_home: int = 0

    # Computed metrics
    role_stable: bool = False
    volatility_flag: bool = False


@dataclass(frozen=True)
class RoleStabilityResult:
    """Result of role stability filter."""
    passed: bool
    role_score: float  # 0-1
    toi_stable: bool
    pp_stable: bool
    flags: List[str]


@dataclass(frozen=True)
class MonteCarloResult:
    """Result of Monte Carlo simulation."""
    p_hit: float  # Probability of hitting
    mean: float
    std: float
    p10: float  # 10th percentile
    p25: float  # 25th percentile
    p50: float  # Median
    p75: float  # 75th percentile
    p90: float  # 90th percentile
    n_sims: int = 150000
