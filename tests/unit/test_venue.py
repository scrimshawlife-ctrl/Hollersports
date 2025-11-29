"""
Unit tests for VenueImpactEngine.

Tests venue loading, modifier application, and edge cases.
"""

from datetime import datetime
from pathlib import Path

import pytest

from hollersports.core.config import Settings
from hollersports.core.models import PlayerProjection
from hollersports.venue import VenueImpactEngine, VenueProfile


class TestVenueProfile:
    """Test VenueProfile model."""

    def test_create_venue_profile(self) -> None:
        """Test basic VenueProfile creation."""
        venue = VenueProfile(
            arena_id="PHX_FOOTPRINT",
            team="PHX",
            name="Footprint Center",
            city="Phoenix",
            altitude_m=331,
            pace_modifier=1.04,
            three_point_modifier=0.98,
            rebound_modifier=0.97,
            home_edge_modifier=1.03,
            tags=["Pace+"],
        )

        assert venue.team == "PHX"
        assert venue.altitude_m == 331
        assert venue.pace_modifier == 1.04

    def test_venue_profile_immutable(self) -> None:
        """Test that VenueProfile is frozen."""
        venue = VenueProfile(
            arena_id="PHX_FOOTPRINT",
            team="PHX",
            name="Footprint Center",
            city="Phoenix",
        )

        with pytest.raises(Exception):  # Pydantic ValidationError
            venue.pace_modifier = 2.0  # type: ignore

    def test_is_high_altitude(self) -> None:
        """Test high altitude detection."""
        denver = VenueProfile(
            arena_id="DEN_BALL_ARENA",
            team="DEN",
            name="Ball Arena",
            city="Denver",
            altitude_m=1609,
            tags=["Altitude"],
        )

        la = VenueProfile(
            arena_id="LAL_CRYPTO",
            team="LAL",
            name="Crypto.com Arena",
            city="Los Angeles",
            altitude_m=87,
        )

        assert denver.is_high_altitude(threshold_m=1000) is True
        assert la.is_high_altitude(threshold_m=1000) is False

    def test_get_display_tags(self) -> None:
        """Test display tag formatting."""
        venue_with_tags = VenueProfile(
            arena_id="DEN_BALL_ARENA",
            team="DEN",
            name="Ball Arena",
            city="Denver",
            altitude_m=1609,
            tags=["Altitude", "Pace+", "3P+"],
        )

        venue_no_tags = VenueProfile(
            arena_id="BKN_BARCLAYS",
            team="BKN",
            name="Barclays Center",
            city="Brooklyn",
        )

        assert venue_with_tags.get_display_tags() == "Altitude, Pace+, 3P+"
        assert venue_no_tags.get_display_tags() == "Neutral"


class TestVenueImpactEngine:
    """Test VenueImpactEngine."""

    def test_init_loads_arenas(self) -> None:
        """Test that engine loads arenas on init."""
        settings = Settings()
        engine = VenueImpactEngine(settings)

        assert engine.num_venues == 30  # 30 NBA teams
        assert "PHX" in engine.teams
        assert "LAL" in engine.teams
        assert "DEN" in engine.teams

    def test_get_venue(self) -> None:
        """Test getting venue by team."""
        engine = VenueImpactEngine()

        phx_venue = engine.get_venue("PHX")
        assert phx_venue.team == "PHX"
        assert phx_venue.name == "Footprint Center"
        assert phx_venue.city == "Phoenix"

    def test_get_venue_not_found(self) -> None:
        """Test getting venue for unknown team raises KeyError."""
        engine = VenueImpactEngine()

        with pytest.raises(KeyError, match="Team 'XXX' not found"):
            engine.get_venue("XXX")

    def test_get_venue_or_default(self) -> None:
        """Test getting venue with fallback to default."""
        engine = VenueImpactEngine()

        # Known team
        phx_venue = engine.get_venue_or_default("PHX")
        assert phx_venue.team == "PHX"
        assert phx_venue.name == "Footprint Center"

        # Unknown team
        unknown_venue = engine.get_venue_or_default("XXX")
        assert unknown_venue.team == "XXX"
        assert unknown_venue.name == "Unknown Arena"
        assert unknown_venue.pace_modifier == 1.0
        assert unknown_venue.three_point_modifier == 1.0

    def test_apply_venue_modifiers(self) -> None:
        """Test applying venue modifiers to projection."""
        engine = VenueImpactEngine()

        # Create base projection
        proj = PlayerProjection(
            player_id="booker123",
            player_name="Devin Booker",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=25.0,
            proj_reb=5.0,
            proj_ast=6.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.5,
            proj_fg3m=3.0,
        )

        # Get PHX venue (pace_modifier=1.04, 3p_modifier=1.02, home_edge=1.03)
        phx_venue = engine.get_venue("PHX")

        # Apply modifiers
        modified_proj = engine.apply_venue_modifiers(proj, phx_venue)

        # Points should be affected by pace (1.04) and home edge (1.03)
        # 25.0 * 1.04 * 1.03 ≈ 26.78
        assert modified_proj.proj_pts > 25.0
        assert modified_proj.proj_pts == pytest.approx(26.78, abs=0.01)

        # 3PM should be affected by pace, 3P modifier, and home edge
        # 3.0 * 1.04 * 1.02 * 1.03 ≈ 3.28
        assert modified_proj.proj_fg3m > 3.0
        assert modified_proj.proj_fg3m == pytest.approx(3.28, abs=0.01)

        # Venue modifier tracking
        assert modified_proj.venue_modifier > 1.0
        assert modified_proj.pace_modifier == pytest.approx(1.04)

    def test_apply_venue_disabled(self) -> None:
        """Test that venue modifiers are skipped when disabled."""
        settings = Settings(venue={"enabled": False})
        engine = VenueImpactEngine(settings)

        proj = PlayerProjection(
            player_id="booker123",
            player_name="Devin Booker",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=25.0,
            proj_reb=5.0,
            proj_ast=6.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.5,
            proj_fg3m=3.0,
        )

        phx_venue = engine.get_venue("PHX")
        modified_proj = engine.apply_venue_modifiers(proj, phx_venue)

        # Should be unchanged
        assert modified_proj.proj_pts == 25.0
        assert modified_proj.proj_fg3m == 3.0
        assert modified_proj.venue_modifier == 1.0

    def test_apply_venue_by_team(self) -> None:
        """Test convenience method to apply venue by team abbreviation."""
        engine = VenueImpactEngine()

        proj = PlayerProjection(
            player_id="jokic123",
            player_name="Nikola Jokic",
            team="DEN",
            matchup_id="DEN_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=26.0,
            proj_reb=12.0,
            proj_ast=9.0,
            proj_stl=1.5,
            proj_blk=0.8,
            proj_tov=3.0,
            proj_fg3m=1.5,
        )

        # Denver has high altitude (pace=1.05, 3p=1.03, home_edge=1.08)
        modified_proj = engine.apply_venue_by_team(proj, "DEN")

        # Points: 26.0 * 1.05 * 1.08 ≈ 29.48
        assert modified_proj.proj_pts == pytest.approx(29.484, abs=0.01)

        # Venue modifier should be significant
        assert modified_proj.venue_modifier > 1.1

    def test_get_venue_display_tag(self) -> None:
        """Test generating display tags for venues."""
        engine = VenueImpactEngine()

        den_tag = engine.get_venue_display_tag("DEN")
        assert "@DEN" in den_tag
        assert "Altitude" in den_tag or "Pace+" in den_tag

        bkn_tag = engine.get_venue_display_tag("BKN")
        assert "@BKN" in bkn_tag

    def test_list_high_altitude_venues(self) -> None:
        """Test listing high altitude venues."""
        engine = VenueImpactEngine()

        high_altitude = engine.list_high_altitude_venues(threshold_m=1000)

        # Should find Denver (1609m) and Utah (1288m)
        teams = [v.team for v in high_altitude]
        assert "DEN" in teams
        assert "UTA" in teams
        assert len(high_altitude) >= 2

    def test_list_pace_boosting_venues(self) -> None:
        """Test listing pace-boosting venues."""
        engine = VenueImpactEngine()

        pace_boost = engine.list_pace_boosting_venues(threshold=1.02)

        # Should find several teams with pace_modifier >= 1.02
        teams = [v.team for v in pace_boost]
        assert "DEN" in teams  # 1.05
        assert "PHX" in teams  # 1.04
        assert "SAC" in teams  # 1.05
        assert len(pace_boost) >= 5

    def test_neutral_venue_no_change(self) -> None:
        """Test that a perfectly neutral venue doesn't change projections."""
        # Create a neutral venue
        neutral_venue = VenueProfile(
            arena_id="NEUTRAL_TEST",
            team="TEST",
            name="Neutral Arena",
            city="Test City",
            altitude_m=0,
            pace_modifier=1.0,
            three_point_modifier=1.0,
            rebound_modifier=1.0,
            home_edge_modifier=1.0,
            tags=[],
        )

        engine = VenueImpactEngine()

        proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="TEST",
            matchup_id="TEST_vs_OTHER_20250124",
            proj_min=30.0,
            proj_pts=20.0,
            proj_reb=5.0,
            proj_ast=4.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.0,
            proj_fg3m=2.0,
        )

        modified = engine.apply_venue_modifiers(proj, neutral_venue)

        # Everything should be unchanged
        assert modified.proj_pts == 20.0
        assert modified.proj_reb == 5.0
        assert modified.proj_ast == 4.0
        assert modified.proj_fg3m == 2.0
        assert modified.venue_modifier == 1.0
        assert modified.pace_modifier == 1.0

    def test_multiple_modifier_stacking(self) -> None:
        """Test that multiple venue modifiers stack correctly."""
        # High pace, high 3P, high home edge venue
        venue = VenueProfile(
            arena_id="STACK_TEST",
            team="TEST",
            name="Stacking Arena",
            city="Test City",
            pace_modifier=1.05,
            three_point_modifier=1.03,
            rebound_modifier=1.02,
            home_edge_modifier=1.04,
            tags=["Pace+", "3P+", "HomeEdge+"],
        )

        engine = VenueImpactEngine()

        proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="TEST",
            matchup_id="TEST_20250124",
            proj_min=30.0,
            proj_pts=20.0,
            proj_reb=5.0,
            proj_ast=4.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.0,
            proj_fg3m=2.0,
        )

        modified = engine.apply_venue_modifiers(proj, venue)

        # Points: 20.0 * 1.05 (pace) * 1.04 (home_edge) = 21.84
        assert modified.proj_pts == pytest.approx(21.84, abs=0.01)

        # Rebounds: 5.0 * 1.05 (pace) * 1.02 (rebound) * 1.04 (home_edge) ≈ 5.60
        assert modified.proj_reb == pytest.approx(5.5944, abs=0.01)

        # 3PM: 2.0 * 1.05 (pace) * 1.03 (3P) * 1.04 (home_edge) ≈ 2.248
        assert modified.proj_fg3m == pytest.approx(2.2484, abs=0.01)

        # Cumulative venue modifier: 1.05 * 1.02 * 1.04 ≈ 1.113
        assert modified.venue_modifier == pytest.approx(1.11384, abs=0.001)
