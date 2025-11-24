"""
Core data models for HollerSports.

All models are immutable (frozen=True) and fully typed for ABX-Core compliance.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class League(str, Enum):
    """Supported leagues."""

    NBA = "nba"
    WNBA = "wnba"
    # Future: NFL, NHL, etc.


class StatCategory(str, Enum):
    """Prop stat categories."""

    POINTS = "points"
    REBOUNDS = "rebounds"
    ASSISTS = "assists"
    STEALS = "steals"
    BLOCKS = "blocks"
    THREE_POINTERS_MADE = "three_pointers_made"
    TURNOVERS = "turnovers"
    FANTASY_SCORE = "fantasy_score"
    PTS_REB_AST = "pts_reb_ast"
    # Combo stats
    PTS_REB = "pts_reb"
    PTS_AST = "pts_ast"
    REB_AST = "reb_ast"


class PlayerStats(BaseModel):
    """Recent statistical profile for a player."""

    player_id: str
    player_name: str
    team: str
    games_played: int = Field(ge=0)

    # Per-game averages
    min_per_game: float = Field(ge=0.0)
    pts_per_game: float = Field(ge=0.0)
    reb_per_game: float = Field(ge=0.0)
    ast_per_game: float = Field(ge=0.0)
    stl_per_game: float = Field(ge=0.0)
    blk_per_game: float = Field(ge=0.0)
    tov_per_game: float = Field(ge=0.0)
    fg3m_per_game: float = Field(ge=0.0)

    # Advanced metrics
    usage_pct: float = Field(default=0.0, description="Usage percentage")
    ast_pct: float = Field(default=0.0, description="Assist percentage")
    reb_pct: float = Field(default=0.0, description="Total rebound percentage")
    ts_pct: float = Field(default=0.0, description="True shooting percentage")

    # Volatility
    pts_std_dev: float = Field(default=0.0, ge=0.0)
    reb_std_dev: float = Field(default=0.0, ge=0.0)
    ast_std_dev: float = Field(default=0.0, ge=0.0)

    model_config = {"frozen": True}


class TeamContext(BaseModel):
    """Team-level context for projections."""

    team_id: str
    team_name: str
    pace: float = Field(description="Possessions per 48 minutes")
    off_rating: float = Field(description="Offensive rating (pts per 100 poss)")
    def_rating: float = Field(description="Defensive rating (pts allowed per 100 poss)")
    net_rating: float = Field(description="Net rating (off - def)")

    # Situational
    is_home: bool
    is_back_to_back: bool = False
    rest_days: int = Field(default=1, ge=0)

    # Injuries/absences
    key_injuries: list[str] = Field(default_factory=list, description="Injured player IDs")

    model_config = {"frozen": True}


class MatchupContext(BaseModel):
    """Full matchup context for a game."""

    matchup_id: str = Field(description="Unique identifier for this matchup")
    league: League
    game_date: datetime
    home_team: TeamContext
    away_team: TeamContext

    # Line info (if available)
    spread: float | None = Field(default=None, description="Point spread (home perspective)")
    total: float | None = Field(default=None, description="Over/under total")

    model_config = {"frozen": True}


class PlayerProjection(BaseModel):
    """
    Base projection for a player in a specific matchup.

    This is the core object that flows through the pipeline:
    1. Created from base statistical models
    2. Enhanced by VenueImpactEngine
    3. Tagged by RolePriorityTagger
    4. Simulated across scripts by GameScriptSimulator
    5. Scored by PropRiskScorer
    """

    player_id: str
    player_name: str
    team: str
    matchup_id: str

    # Projected stats (medians)
    proj_min: float = Field(ge=0.0)
    proj_pts: float = Field(ge=0.0)
    proj_reb: float = Field(ge=0.0)
    proj_ast: float = Field(ge=0.0)
    proj_stl: float = Field(ge=0.0)
    proj_blk: float = Field(ge=0.0)
    proj_tov: float = Field(ge=0.0)
    proj_fg3m: float = Field(ge=0.0)

    # Uncertainty (std dev)
    pts_std: float = Field(default=0.0, ge=0.0)
    reb_std: float = Field(default=0.0, ge=0.0)
    ast_std: float = Field(default=0.0, ge=0.0)

    # Modifiers applied (for transparency)
    venue_modifier: float = Field(default=1.0, description="Cumulative venue modifier applied")
    pace_modifier: float = Field(default=1.0, description="Pace adjustment applied")

    # Provenance
    base_model_version: str = Field(default="v0.1.0")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"frozen": False}  # Allow mutation as it flows through pipeline

    def apply_modifier(self, stat: StatCategory, modifier: float) -> None:
        """
        Apply a multiplicative modifier to a projected stat.

        Args:
            stat: Which stat to modify
            modifier: Multiplicative factor (1.0 = no change)
        """
        if stat == StatCategory.POINTS:
            self.proj_pts *= modifier
        elif stat == StatCategory.REBOUNDS:
            self.proj_reb *= modifier
        elif stat == StatCategory.ASSISTS:
            self.proj_ast *= modifier
        elif stat == StatCategory.STEALS:
            self.proj_stl *= modifier
        elif stat == StatCategory.BLOCKS:
            self.proj_blk *= modifier
        elif stat == StatCategory.THREE_POINTERS_MADE:
            self.proj_fg3m *= modifier
        elif stat == StatCategory.TURNOVERS:
            self.proj_tov *= modifier

    def get_stat_value(self, stat: StatCategory) -> float:
        """
        Get projected value for a given stat category.

        Args:
            stat: Stat category to retrieve

        Returns:
            Projected value
        """
        stat_map = {
            StatCategory.POINTS: self.proj_pts,
            StatCategory.REBOUNDS: self.proj_reb,
            StatCategory.ASSISTS: self.proj_ast,
            StatCategory.STEALS: self.proj_stl,
            StatCategory.BLOCKS: self.proj_blk,
            StatCategory.THREE_POINTERS_MADE: self.proj_fg3m,
            StatCategory.TURNOVERS: self.proj_tov,
            StatCategory.PTS_REB_AST: self.proj_pts + self.proj_reb + self.proj_ast,
            StatCategory.PTS_REB: self.proj_pts + self.proj_reb,
            StatCategory.PTS_AST: self.proj_pts + self.proj_ast,
            StatCategory.REB_AST: self.proj_reb + self.proj_ast,
        }
        return stat_map.get(stat, 0.0)

    def get_stat_std(self, stat: StatCategory) -> float:
        """
        Get standard deviation for a stat (for uncertainty modeling).

        Args:
            stat: Stat category

        Returns:
            Standard deviation
        """
        # For combo stats, use Pythagorean sum
        if stat == StatCategory.PTS_REB_AST:
            return (self.pts_std**2 + self.reb_std**2 + self.ast_std**2) ** 0.5
        elif stat == StatCategory.PTS_REB:
            return (self.pts_std**2 + self.reb_std**2) ** 0.5
        elif stat == StatCategory.PTS_AST:
            return (self.pts_std**2 + self.ast_std**2) ** 0.5
        elif stat == StatCategory.REB_AST:
            return (self.reb_std**2 + self.ast_std**2) ** 0.5

        stat_std_map = {
            StatCategory.POINTS: self.pts_std,
            StatCategory.REBOUNDS: self.reb_std,
            StatCategory.ASSISTS: self.ast_std,
        }
        return stat_std_map.get(stat, 0.0)


class PropSide(str, Enum):
    """Which side of a prop line."""

    OVER = "over"
    UNDER = "under"


class PropLine(BaseModel):
    """A betting line for a player prop."""

    player_id: str
    player_name: str
    matchup_id: str
    stat: StatCategory
    line: float
    over_odds: int = Field(description="American odds for over (e.g. -110)")
    under_odds: int = Field(description="American odds for under")
    sportsbook: str = Field(default="generic")

    model_config = {"frozen": True}

    def implied_prob(self, side: PropSide) -> float:
        """
        Convert American odds to implied probability.

        Args:
            side: Which side of the line

        Returns:
            Implied probability (0-1)
        """
        odds = self.over_odds if side == PropSide.OVER else self.under_odds
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        else:
            return 100 / (odds + 100)
