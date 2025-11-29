"""
Venue Impact models.

Defines VenueProfile and related structures for arena characteristics.
"""

from pydantic import BaseModel, Field


class VenueProfile(BaseModel):
    """
    Arena characteristics that impact player performance.

    All modifiers are multiplicative (1.0 = no effect).
    """

    arena_id: str = Field(description="Unique arena identifier (e.g., 'PHX_FOOTPRINT')")
    team: str = Field(description="Home team abbreviation (e.g., 'PHX')")
    name: str = Field(description="Arena name")
    city: str = Field(description="City location")

    # Physical characteristics
    altitude_m: int = Field(default=0, ge=0, description="Altitude in meters above sea level")

    # Performance modifiers
    pace_modifier: float = Field(
        default=1.0, ge=0.8, le=1.2, description="Pace adjustment (1.0 = neutral)"
    )
    three_point_modifier: float = Field(
        default=1.0, ge=0.8, le=1.2, description="3P shooting adjustment (1.0 = neutral)"
    )
    rebound_modifier: float = Field(
        default=1.0, ge=0.8, le=1.2, description="Rebounding adjustment (1.0 = neutral)"
    )
    home_edge_modifier: float = Field(
        default=1.0, ge=0.95, le=1.15, description="General home court advantage (1.0 = neutral)"
    )

    # Environmental tags
    tags: list[str] = Field(
        default_factory=list, description="Tags like 'altitude', 'pace+', '3P-', etc."
    )

    model_config = {"frozen": True}

    def get_display_tags(self) -> str:
        """
        Get formatted display string for UI.

        Returns:
            Formatted string like "Pace+, 3P-" or "Altitude, Pace+"
        """
        if not self.tags:
            return "Neutral"
        return ", ".join(self.tags)

    def is_high_altitude(self, threshold_m: int = 1000) -> bool:
        """
        Check if venue is at high altitude.

        Args:
            threshold_m: Altitude threshold in meters

        Returns:
            True if above threshold
        """
        return self.altitude_m >= threshold_m
