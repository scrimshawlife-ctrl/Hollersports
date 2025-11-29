"""
Role tagging models.

Defines player role taxonomy and RoleTag structures.
"""

from enum import Enum

from pydantic import BaseModel, Field


class PlayerRole(str, Enum):
    """
    Player role taxonomy for contextual projection adjustments.

    Roles are inferred from recent stats, usage patterns, and team context.
    """

    # Primary scoring roles
    USAGE_HINGE = "usage_hinge"  # High-usage primary scorer (USG% > 28%)
    TUNNEL_SCORER = "tunnel_scorer"  # High-volume, low-assist scorer
    BENCH_MICROWAVE = "bench_microwave"  # Scoring punch off the bench

    # Facilitation roles
    CONNECTOR = "connector"  # Playmaking glue guy (moderate everything, high AST%)
    PRIMARY_PLAYMAKER = "primary_playmaker"  # High AST%, high USG%

    # Specialist roles
    GLASS_CLEANER = "glass_cleaner"  # Rebounding specialist (TRB% > 18%)
    GRAVITY_ONLY = "gravity_only"  # Spacing/attention without the ball
    THREE_AND_D = "three_and_d"  # 3-point shooting and defense specialist
    RIM_PROTECTOR = "rim_protector"  # Shot-blocking specialist

    # Versatile roles
    ALL_AROUND = "all_around"  # Balanced across multiple stats
    ROLE_PLAYER = "role_player"  # Limited usage, specific function

    # Unknown/insufficient data
    UNKNOWN = "unknown"


class RoleTag(BaseModel):
    """
    Role tag with confidence score for a player in a specific context.

    Confidence is reduced by:
    - Insufficient recent games
    - Mixed/inconsistent statistical signals
    - Borderline thresholds
    """

    role: PlayerRole = Field(description="Inferred player role")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in this role assignment (0-1)"
    )
    notes: dict[str, float] = Field(
        default_factory=dict, description="Supporting signals (e.g., usg_pct, ast_pct)"
    )

    model_config = {"frozen": True}

    def get_display_label(self) -> str:
        """
        Get formatted display label for UI.

        Returns:
            Formatted string like "usage_hinge (0.85)" or "glass_cleaner (0.72)"
        """
        return f"{self.role.value} ({self.confidence:.2f})"

    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        """
        Check if role assignment is high confidence.

        Args:
            threshold: Confidence threshold

        Returns:
            True if confidence >= threshold
        """
        return self.confidence >= threshold

    def is_scorer_role(self) -> bool:
        """Check if role is primarily a scoring role."""
        return self.role in {
            PlayerRole.USAGE_HINGE,
            PlayerRole.TUNNEL_SCORER,
            PlayerRole.BENCH_MICROWAVE,
        }

    def is_facilitator_role(self) -> bool:
        """Check if role is primarily a facilitating role."""
        return self.role in {PlayerRole.CONNECTOR, PlayerRole.PRIMARY_PLAYMAKER}

    def is_specialist_role(self) -> bool:
        """Check if role is a specialist (glass, gravity, 3D, rim protection)."""
        return self.role in {
            PlayerRole.GLASS_CLEANER,
            PlayerRole.GRAVITY_ONLY,
            PlayerRole.THREE_AND_D,
            PlayerRole.RIM_PROTECTOR,
        }
