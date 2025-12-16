"""
Type definitions for NFL Script-Conditioned Median Floor (SCMF) engine.

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


class Market(str, Enum):
    """NFL prop markets"""
    RECEPTIONS = "RECEPTIONS"
    REC_YDS = "REC_YDS"
    RUSH_YDS = "RUSH_YDS"
    RUSH_ATT = "RUSH_ATT"
    TARGETS = "TARGETS"
    PASS_ATT = "PASS_ATT"
    PASS_YDS = "PASS_YDS"
    # Event stats (forbidden in ultra-safe mode)
    REC_TD = "REC_TD"
    RUSH_TD = "RUSH_TD"
    PASS_TD = "PASS_TD"


class ScriptState(str, Enum):
    """Game script states that affect player usage"""
    NEUTRAL = "NEUTRAL"
    LEADING = "LEADING"
    TRAILING = "TRAILING"
    TWO_MINUTE = "TWO_MINUTE"


@dataclass(frozen=True)
class NFLGameRow:
    """
    Single player-game observation from input dataset.
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
    position: str  # WR, TE, RB, QB

    # Core stats
    snaps: int
    targets: int
    receptions: int
    receiving_yards: float
    rushing_attempts: int
    rushing_yards: float

    # Optional stats
    routes: Optional[int] = None
    pass_attempts: Optional[int] = None
    pass_yards: Optional[float] = None

    # Vegas context (optional)
    vegas_spread: Optional[float] = None  # Negative = team favored
    vegas_total: Optional[float] = None

    # Team context (optional)
    team_pass_rate_over_expected: Optional[float] = None  # PROE
    opponent_pass_def_proxy: Optional[float] = None
    opponent_rush_def_proxy: Optional[float] = None

    # Prop line (for backtest)
    line: Optional[float] = None


@dataclass(frozen=True)
class NFLContext:
    """
    Game context for script state modeling.
    """
    game_id: str
    team: str
    opponent: str
    is_home: bool
    vegas_spread: Optional[float] = None
    vegas_total: Optional[float] = None
    team_proe: Optional[float] = None


@dataclass(frozen=True)
class PropLeg:
    """
    A prop bet specification.
    """
    player_id: str
    player_name: str
    market: Market
    line: float
    side: Side
    game_id: Optional[str] = None


@dataclass(frozen=True)
class Projection:
    """
    Complete projection with script conditioning.
    """
    player_id: str
    player_name: str
    position: str
    game_id: str
    market: Market

    # Core statistics
    mu: float  # Mean projection (blended across scripts)
    sigma: float  # Standard deviation
    median: float  # Median estimate
    floor: float  # Conservative floor

    # Script-specific projections
    script_mus: Dict[str, float]  # mu per script state
    script_priors: Dict[str, float]  # probability of each script

    # Probability & confidence
    p_hit: float  # Monte Carlo hit probability
    confidence: float  # Overall confidence (0-1)

    # Context
    line: float
    side: Side

    # Explanation
    reasons: List[str]
    flags: List[str]

    # Provenance
    provenance_hash: str

    # Additional metrics
    role_score: float = 0.0
    opponent_modifier: float = 0.0
    survivability_score: float = 0.0


@dataclass(frozen=True)
class SlatePickResult:
    """
    Result of picker algorithm on a slate.
    """
    ultra_safe_3leg: List[Projection]
    ultra_safe_5leg: List[Projection]

    # Alternative configurations
    correlated_5leg: Optional[List[Projection]] = None
    balanced_5leg: Optional[List[Projection]] = None
    ladder_variant: Optional[List[Projection]] = None

    # Metadata
    total_candidates: int = 0
    filtered_candidates: int = 0
    provenance_hash: str = ""


@dataclass
class FeatureSet:
    """
    Computed features for a player-game.
    """
    player_id: str
    game_id: str
    position: str

    # Historical stats
    last5_targets: List[int]
    last5_receptions: List[int]
    last5_routes: List[int]
    last5_snaps: List[int]
    last5_rush_att: List[int]

    # Season medians
    season_targets_median: float
    season_receptions_median: float
    season_routes_median: float
    season_snaps_median: float

    # Share metrics
    target_share_proxy: float = 0.0
    route_participation: float = 0.0
    rush_share: float = 0.0
    snap_share: float = 0.0

    # Stability flags
    role_stable: bool = False
    volatility_flag: bool = False


@dataclass(frozen=True)
class RoleStabilityResult:
    """Result of role stability filter."""
    passed: bool
    role_score: float
    position: str
    routes_stable: bool = False
    snaps_stable: bool = False
    targets_stable: bool = False
    flags: List[str] = None

    def __post_init__(self):
        if self.flags is None:
            object.__setattr__(self, 'flags', [])


@dataclass(frozen=True)
class MonteCarloResult:
    """Result of Monte Carlo simulation."""
    p_hit: float
    mean: float
    std: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    n_sims: int = 150000


# Event markets (forbidden in ultra-safe mode)
EVENT_MARKETS = {Market.REC_TD, Market.RUSH_TD, Market.PASS_TD}

# High survivability markets (preferred in ultra-safe)
HIGH_SURVIVABILITY_MARKETS = {Market.RECEPTIONS, Market.TARGETS}

# Medium survivability markets (acceptable)
MEDIUM_SURVIVABILITY_MARKETS = {Market.REC_YDS, Market.RUSH_YDS, Market.RUSH_ATT}
