"""
Prop risk scoring models.

Defines unified risk profile combining venue, role, and script analysis.
"""

from typing import Literal

from pydantic import BaseModel, Field

from hollersports.roles.models import RoleTag
from hollersports.scripts.models import FragilityAnalysis
from hollersports.venue.models import VenueProfile


class PropRiskProfile(BaseModel):
    """
    Unified risk profile for a player prop.

    Combines:
    - Base projection with venue adjustments
    - Role context
    - Script fragility analysis
    - Line evaluation and expected value

    Into a single risk score with recommendation.
    """

    # Identifiers
    player_id: str
    player_name: str
    stat: str = Field(description="Stat category (e.g., 'points', 'rebounds')")
    line: float = Field(description="Book line being evaluated")

    # Core risk metrics
    value_score: float = Field(
        description="Expected edge vs book line (-1 to 1, positive = +EV)"
    )
    volatility_score: float = Field(
        ge=0.0, le=1.0, description="Outcome variance (0=stable, 1=volatile)"
    )
    fragility_index: float = Field(
        ge=0.0, le=1.0, description="Script dependence (0=robust, 1=fragile)"
    )

    # Recommendation
    recommended_side: Literal["higher", "lower", "avoid"] = Field(
        description="Recommended position"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in recommendation (0-1)"
    )

    # Contextual information
    venue_profile: VenueProfile | None = Field(default=None)
    role_tag: RoleTag | None = Field(default=None)
    fragility_analysis: FragilityAnalysis | None = Field(default=None)

    # Derived metrics
    projected_value: float = Field(description="Script-weighted projection")
    implied_prob_over: float = Field(
        ge=0.0, le=1.0, description="Implied probability of going over"
    )
    expected_value: float = Field(description="Expected value in units")

    # Tags for UI
    risk_tags: list[str] = Field(default_factory=list, description="Risk warning tags")
    venue_tags: list[str] = Field(
        default_factory=list, description="Venue characteristic tags"
    )

    model_config = {"frozen": False}

    def is_plus_ev(self, threshold: float = 0.03) -> bool:
        """
        Check if prop has positive expected value.

        Args:
            threshold: Minimum EV threshold (default 3%)

        Returns:
            True if value_score >= threshold
        """
        return self.value_score >= threshold

    def is_high_risk(self) -> bool:
        """
        Check if prop is high risk.

        High risk = high volatility OR high fragility.

        Returns:
            True if volatility > 0.7 or fragility > 0.6
        """
        return self.volatility_score > 0.7 or self.fragility_index > 0.6

    def is_recommended(self) -> bool:
        """
        Check if prop is recommended (not 'avoid').

        Returns:
            True if recommended_side is 'higher' or 'lower'
        """
        return self.recommended_side in ["higher", "lower"]

    def get_risk_level(self) -> Literal["low", "medium", "high"]:
        """
        Get qualitative risk level.

        Returns:
            "low", "medium", or "high"
        """
        # Combine volatility and fragility
        risk_score = (self.volatility_score + self.fragility_index) / 2

        if risk_score < 0.3:
            return "low"
        elif risk_score < 0.6:
            return "medium"
        else:
            return "high"

    def get_summary_string(self) -> str:
        """
        Get one-line summary for display.

        Returns:
            Formatted summary string
        """
        side = self.recommended_side.upper()
        risk = self.get_risk_level()
        ev = f"{self.value_score:+.1%}"

        return f"{self.player_name} {self.stat} {side} {self.line} | EV: {ev} | Risk: {risk} | Fragility: {self.fragility_index:.2f}"
