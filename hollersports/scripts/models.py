"""
Game script models.

Defines game script taxonomy and script projection structures.
"""

from enum import Enum

from pydantic import BaseModel, Field


class GameScript(str, Enum):
    """
    Game script taxonomy for scenario-based projections.

    Scripts represent different game flow patterns that affect
    player opportunity and statistical output.
    """

    PACE_UP = "pace_up"  # High-tempo game (more possessions than expected)
    PACE_DOWN = "pace_down"  # Slow-tempo game (fewer possessions)
    SHOOTOUT = "shootout"  # High-scoring, offensive game
    GRIND = "grind"  # Low-scoring, defensive struggle
    BLOWOUT = "blowout"  # Lopsided game (starters sit early, bench plays)
    BALANCED = "balanced"  # Normal, competitive game


class ScriptProjection(BaseModel):
    """
    Projection for a specific game script scenario.

    Represents how a player's stats would project under a particular
    game flow (e.g., pace_up, shootout, etc.).
    """

    script: GameScript = Field(description="Game script type")
    probability: float = Field(ge=0.0, le=1.0, description="Probability of this script (0-1)")

    # Adjusted projections under this script
    proj_pts: float = Field(ge=0.0, description="Points projection in this script")
    proj_reb: float = Field(ge=0.0, description="Rebounds projection in this script")
    proj_ast: float = Field(ge=0.0, description="Assists projection in this script")

    # Statistical spread
    std_dev: float = Field(ge=0.0, description="Standard deviation of outcome")

    # Line evaluation
    line: float | None = Field(default=None, description="Book line being evaluated")
    p_hit_line: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Probability of hitting line in this script"
    )

    model_config = {"frozen": True}

    def get_expected_value(self, stat: str = "pts") -> float:
        """
        Get expected value for a stat in this script.

        Args:
            stat: Stat to retrieve (pts, reb, ast)

        Returns:
            Projected value
        """
        if stat == "pts":
            return self.proj_pts
        elif stat == "reb":
            return self.proj_reb
        elif stat == "ast":
            return self.proj_ast
        else:
            return 0.0


class FragilityAnalysis(BaseModel):
    """
    Fragility analysis across multiple game scripts.

    Measures how dependent a prop is on a specific narrow script.
    """

    scripts: list[ScriptProjection] = Field(
        description="All script projections for this player/prop"
    )
    fragility_index: float = Field(
        ge=0.0, le=1.0, description="Fragility score (0=robust, 1=very fragile)"
    )
    dominant_script: GameScript | None = Field(
        default=None, description="Script most responsible for prop hitting"
    )
    script_diversity: float = Field(
        ge=0.0, le=1.0, description="How evenly distributed prob mass is across scripts"
    )

    # Summary stats
    weighted_mean: float = Field(description="Probability-weighted mean projection")
    weighted_std: float = Field(ge=0.0, description="Probability-weighted std dev")

    model_config = {"frozen": False}

    def get_script_hit_rate(self, script: GameScript) -> float | None:
        """
        Get hit rate for a specific script.

        Args:
            script: Script to query

        Returns:
            Hit rate (p_hit_line) for that script, or None if not found
        """
        for sp in self.scripts:
            if sp.script == script and sp.p_hit_line is not None:
                return sp.p_hit_line
        return None

    def get_scripts_hitting(self, threshold: float = 0.5) -> list[GameScript]:
        """
        Get list of scripts where p_hit_line > threshold.

        Args:
            threshold: Probability threshold (default 0.5)

        Returns:
            List of GameScript values where line is likely to hit
        """
        hitting = []
        for sp in self.scripts:
            if sp.p_hit_line is not None and sp.p_hit_line > threshold:
                hitting.append(sp.script)
        return hitting

    def is_fragile(self, threshold: float = 0.6) -> bool:
        """
        Check if prop is considered fragile.

        Args:
            threshold: Fragility index threshold

        Returns:
            True if fragility_index >= threshold
        """
        return self.fragility_index >= threshold

    def is_robust(self, threshold: float = 0.3) -> bool:
        """
        Check if prop is considered robust.

        Args:
            threshold: Robustness threshold (lower fragility)

        Returns:
            True if fragility_index <= threshold
        """
        return self.fragility_index <= threshold
