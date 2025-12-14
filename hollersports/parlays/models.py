"""
Parlay construction models.

Defines parlay legs, parlays, and build modes.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from hollersports.props.models import PropRiskProfile


class ParlayMode(str, Enum):
    """
    Parlay construction mode.

    Determines risk tolerance and filtering criteria.
    """

    CONSERVATIVE = "conservative"  # Low fragility, high confidence
    BALANCED = "balanced"  # Medium risk/reward
    AGGRESSIVE = "aggressive"  # Higher risk for better multipliers


class ParlayLeg(BaseModel):
    """
    Single leg of a parlay.

    Wraps PropRiskProfile with additional parlay-specific metadata.
    """

    prop_risk_profile: PropRiskProfile
    odds: int = Field(description="American odds for this leg (e.g., -110)")

    # Derived fields
    decimal_odds: float = Field(description="Decimal odds (e.g., 1.909)")
    implied_prob: float = Field(ge=0.0, le=1.0, description="Implied probability")

    model_config = {"frozen": False}

    def model_post_init(self, __context: object) -> None:
        """Calculate derived fields after initialization."""
        # Convert American odds to decimal
        if self.odds < 0:
            self.decimal_odds = 1 + (100 / abs(self.odds))
        else:
            self.decimal_odds = 1 + (self.odds / 100)

        # Calculate implied probability
        if self.odds < 0:
            self.implied_prob = abs(self.odds) / (abs(self.odds) + 100)
        else:
            self.implied_prob = 100 / (self.odds + 100)

    def get_display_string(self) -> str:
        """
        Get formatted display string for this leg.

        Returns:
            Formatted string with player, stat, side, line
        """
        profile = self.prop_risk_profile
        side = profile.recommended_side.upper()
        return f"{profile.player_name} {profile.stat} {side} {profile.line}"


class Parlay(BaseModel):
    """
    Multi-leg parlay with risk analysis.

    Combines multiple PropRiskProfile objects with diversification checks.
    """

    parlay_id: str = Field(description="Unique identifier")
    mode: ParlayMode = Field(description="Construction mode used")
    legs: list[ParlayLeg] = Field(description="Parlay legs")

    # Aggregate metrics
    combined_odds: float = Field(description="Combined decimal odds")
    combined_implied_prob: float = Field(
        ge=0.0, le=1.0, description="Combined implied probability"
    )
    expected_hit_prob: float = Field(
        ge=0.0, le=1.0, description="Expected probability all legs hit"
    )

    # Risk metrics
    avg_fragility: float = Field(ge=0.0, le=1.0, description="Average fragility across legs")
    avg_confidence: float = Field(ge=0.0, le=1.0, description="Average confidence across legs")
    avg_value_score: float = Field(description="Average value score across legs")

    # Diversification
    num_unique_games: int = Field(ge=1, description="Number of unique games covered")
    num_unique_stats: int = Field(ge=1, description="Number of unique stat types")

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Parlay-level tags")

    model_config = {"frozen": False}

    def get_potential_payout(self, stake: float = 100.0) -> float:
        """
        Calculate potential payout for a given stake.

        Args:
            stake: Bet amount (default $100)

        Returns:
            Total payout (stake + winnings)
        """
        return stake * self.combined_odds

    def get_potential_profit(self, stake: float = 100.0) -> float:
        """
        Calculate potential profit for a given stake.

        Args:
            stake: Bet amount (default $100)

        Returns:
            Profit (winnings only, not including stake)
        """
        return self.get_potential_payout(stake) - stake

    def get_expected_value(self, stake: float = 100.0) -> float:
        """
        Calculate expected value for this parlay.

        Args:
            stake: Bet amount (default $100)

        Returns:
            Expected value in dollars
        """
        payout = self.get_potential_payout(stake)
        ev = (self.expected_hit_prob * payout) - stake
        return ev

    def is_positive_ev(self) -> bool:
        """
        Check if parlay has positive expected value.

        Returns:
            True if expected value > 0
        """
        return self.get_expected_value() > 0

    def get_risk_level(self) -> Literal["low", "medium", "high"]:
        """
        Get qualitative risk level for this parlay.

        Returns:
            "low", "medium", or "high"
        """
        # Combine fragility and confidence
        risk_score = self.avg_fragility - (self.avg_confidence * 0.5)

        if risk_score < 0.2:
            return "low"
        elif risk_score < 0.5:
            return "medium"
        else:
            return "high"

    def get_summary_string(self) -> str:
        """
        Get one-line summary for display.

        Returns:
            Formatted summary string
        """
        num_legs = len(self.legs)
        odds = f"+{int((self.combined_odds - 1) * 100)}"
        ev = f"{self.get_expected_value():+.2f}"
        risk = self.get_risk_level()

        return f"{num_legs}-leg {self.mode.value} | {odds} | EV: ${ev} | Risk: {risk} | Avg Frag: {self.avg_fragility:.2f}"
