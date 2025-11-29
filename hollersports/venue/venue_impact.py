"""
VenueImpactEngine - Apply arena-specific modifiers to projections.

Responsibilities:
- Load and cache arena dataset
- Provide venue lookup by team
- Apply venue modifiers to PlayerProjection objects
- Track provenance of modifications
"""

import json
from pathlib import Path
from typing import Optional

from hollersports.core.config import Settings, get_settings
from hollersports.core.models import PlayerProjection, StatCategory
from hollersports.venue.models import VenueProfile


class VenueImpactEngine:
    """
    Engine for applying venue-specific effects to player projections.

    Loads arena data once, caches it, and provides methods to:
    - Retrieve venue profiles by team
    - Apply modifiers to projections
    - Generate UI-friendly venue tags
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize VenueImpactEngine.

        Args:
            settings: Settings instance (will load default if not provided)
        """
        self.settings = settings or get_settings()
        self._venues: dict[str, VenueProfile] = {}
        self._load_arenas()

    def _load_arenas(self) -> None:
        """
        Load arena dataset from config file.

        Raises:
            FileNotFoundError: If arenas data file doesn't exist
            ValueError: If arenas data is malformed
        """
        arenas_path = Path(self.settings.venue.arenas_data_path)

        if not arenas_path.exists():
            raise FileNotFoundError(
                f"Arenas data not found at {arenas_path}. "
                f"Expected venue data at {self.settings.venue.arenas_data_path}"
            )

        with open(arenas_path, "r") as f:
            data = json.load(f)

        if "arenas" not in data:
            raise ValueError("Arenas data must contain 'arenas' key")

        # Parse and cache venues
        for arena_data in data["arenas"]:
            venue = VenueProfile(**arena_data)
            self._venues[venue.team] = venue

    def get_venue(self, team: str) -> VenueProfile:
        """
        Get venue profile for a team.

        Args:
            team: Team abbreviation (e.g., 'PHX', 'LAL')

        Returns:
            VenueProfile for the team

        Raises:
            KeyError: If team not found in venue database
        """
        if team not in self._venues:
            raise KeyError(
                f"Team '{team}' not found in venue database. "
                f"Available teams: {sorted(self._venues.keys())}"
            )
        return self._venues[team]

    def get_venue_or_default(self, team: str) -> VenueProfile:
        """
        Get venue profile for a team, or return neutral default if not found.

        Args:
            team: Team abbreviation

        Returns:
            VenueProfile (real or default neutral)
        """
        try:
            return self.get_venue(team)
        except KeyError:
            # Return neutral default
            return VenueProfile(
                arena_id=f"{team}_UNKNOWN",
                team=team,
                name="Unknown Arena",
                city="Unknown",
                altitude_m=0,
                pace_modifier=self.settings.venue.default_pace_modifier,
                three_point_modifier=self.settings.venue.default_three_point_modifier,
                rebound_modifier=1.0,
                home_edge_modifier=1.0,
                tags=[],
            )

    def apply_venue_modifiers(
        self, projection: PlayerProjection, venue: VenueProfile
    ) -> PlayerProjection:
        """
        Apply venue modifiers to a player projection.

        Modifies the projection in-place and returns it for chaining.

        Args:
            projection: PlayerProjection to modify
            venue: VenueProfile with modifiers to apply

        Returns:
            Modified PlayerProjection (same object, mutated)
        """
        if not self.settings.venue.enabled:
            # Venue adjustments disabled, return unchanged
            return projection

        # Apply pace modifier to volume stats (pts, reb, ast, etc.)
        # Pace affects opportunity, so all counting stats scale
        if venue.pace_modifier != 1.0:
            projection.proj_pts *= venue.pace_modifier
            projection.proj_reb *= venue.pace_modifier
            projection.proj_ast *= venue.pace_modifier
            projection.proj_stl *= venue.pace_modifier
            projection.proj_blk *= venue.pace_modifier
            projection.proj_tov *= venue.pace_modifier
            projection.proj_fg3m *= venue.pace_modifier

            # Update pace modifier tracking
            projection.pace_modifier *= venue.pace_modifier

        # Apply 3P modifier specifically to three-point makes
        if venue.three_point_modifier != 1.0:
            projection.proj_fg3m *= venue.three_point_modifier

        # Apply rebound modifier
        if venue.rebound_modifier != 1.0:
            projection.proj_reb *= venue.rebound_modifier

        # Apply general home edge (slight boost to all stats)
        # This represents the intangible home court advantage
        if venue.home_edge_modifier != 1.0:
            edge = venue.home_edge_modifier
            projection.proj_pts *= edge
            projection.proj_reb *= edge
            projection.proj_ast *= edge
            projection.proj_stl *= edge
            projection.proj_blk *= edge

        # Calculate cumulative venue modifier for transparency
        cumulative_modifier = (
            venue.pace_modifier * venue.rebound_modifier * venue.home_edge_modifier
        )
        projection.venue_modifier *= cumulative_modifier

        return projection

    def apply_venue_by_team(
        self, projection: PlayerProjection, home_team: str
    ) -> PlayerProjection:
        """
        Convenience method to apply venue modifiers by team abbreviation.

        Args:
            projection: PlayerProjection to modify
            home_team: Home team abbreviation (determines venue)

        Returns:
            Modified PlayerProjection
        """
        venue = self.get_venue_or_default(home_team)
        return self.apply_venue_modifiers(projection, venue)

    def get_venue_display_tag(self, team: str) -> str:
        """
        Get formatted display tag for a venue.

        Args:
            team: Team abbreviation

        Returns:
            Formatted string like "@DEN (Altitude, Pace+)" or "@LAL (Neutral)"
        """
        venue = self.get_venue_or_default(team)
        tag_str = venue.get_display_tags()
        return f"@{team} ({tag_str})"

    def list_high_altitude_venues(self, threshold_m: int = 1000) -> list[VenueProfile]:
        """
        List all venues above a certain altitude.

        Args:
            threshold_m: Altitude threshold in meters

        Returns:
            List of VenueProfile objects above threshold
        """
        return [v for v in self._venues.values() if v.is_high_altitude(threshold_m)]

    def list_pace_boosting_venues(self, threshold: float = 1.02) -> list[VenueProfile]:
        """
        List venues that boost pace significantly.

        Args:
            threshold: Pace modifier threshold

        Returns:
            List of VenueProfile objects with pace_modifier >= threshold
        """
        return [v for v in self._venues.values() if v.pace_modifier >= threshold]

    @property
    def num_venues(self) -> int:
        """Get number of venues loaded."""
        return len(self._venues)

    @property
    def teams(self) -> list[str]:
        """Get list of all team abbreviations."""
        return sorted(self._venues.keys())
