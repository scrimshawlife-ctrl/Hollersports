"""
Unit tests for core data models.

Tests model validation, immutability, and methods.
"""

from datetime import datetime

import pytest

from hollersports.core.models import (
    League,
    MatchupContext,
    PlayerProjection,
    PlayerStats,
    PropLine,
    PropSide,
    StatCategory,
    TeamContext,
)


class TestPlayerStats:
    """Test PlayerStats model."""

    def test_create_player_stats(self) -> None:
        """Test basic PlayerStats creation."""
        stats = PlayerStats(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            games_played=10,
            min_per_game=32.5,
            pts_per_game=25.3,
            reb_per_game=6.2,
            ast_per_game=4.1,
            stl_per_game=1.2,
            blk_per_game=0.8,
            tov_per_game=2.1,
            fg3m_per_game=2.5,
            usage_pct=28.5,
            ast_pct=22.3,
            reb_pct=12.1,
            ts_pct=0.615,
        )

        assert stats.player_id == "player123"
        assert stats.pts_per_game == 25.3
        assert stats.usage_pct == 28.5

    def test_player_stats_immutable(self) -> None:
        """Test that PlayerStats is frozen."""
        stats = PlayerStats(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            games_played=10,
            min_per_game=30.0,
            pts_per_game=20.0,
            reb_per_game=5.0,
            ast_per_game=3.0,
            stl_per_game=1.0,
            blk_per_game=0.5,
            tov_per_game=2.0,
            fg3m_per_game=2.0,
        )

        with pytest.raises(Exception):  # Pydantic will raise ValidationError
            stats.pts_per_game = 30.0  # type: ignore


class TestPlayerProjection:
    """Test PlayerProjection model."""

    def test_create_projection(self) -> None:
        """Test basic PlayerProjection creation."""
        proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=32.0,
            proj_pts=24.5,
            proj_reb=6.3,
            proj_ast=4.2,
            proj_stl=1.1,
            proj_blk=0.7,
            proj_tov=2.0,
            proj_fg3m=2.3,
        )

        assert proj.player_name == "Test Player"
        assert proj.proj_pts == 24.5

    def test_apply_modifier(self) -> None:
        """Test applying stat modifiers."""
        proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=30.0,
            proj_pts=20.0,
            proj_reb=5.0,
            proj_ast=4.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.0,
            proj_fg3m=2.0,
        )

        # Apply 10% boost to points
        proj.apply_modifier(StatCategory.POINTS, 1.1)
        assert proj.proj_pts == pytest.approx(22.0)

        # Apply pace modifier to rebounds
        proj.apply_modifier(StatCategory.REBOUNDS, 1.05)
        assert proj.proj_reb == pytest.approx(5.25)

    def test_get_stat_value(self) -> None:
        """Test getting stat values."""
        proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=30.0,
            proj_pts=20.0,
            proj_reb=5.0,
            proj_ast=4.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.0,
            proj_fg3m=2.0,
        )

        assert proj.get_stat_value(StatCategory.POINTS) == 20.0
        assert proj.get_stat_value(StatCategory.REBOUNDS) == 5.0
        assert proj.get_stat_value(StatCategory.PTS_REB_AST) == 29.0
        assert proj.get_stat_value(StatCategory.PTS_REB) == 25.0

    def test_get_stat_std(self) -> None:
        """Test getting stat standard deviations."""
        proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=30.0,
            proj_pts=20.0,
            proj_reb=5.0,
            proj_ast=4.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.0,
            proj_fg3m=2.0,
            pts_std=3.0,
            reb_std=2.0,
            ast_std=1.5,
        )

        assert proj.get_stat_std(StatCategory.POINTS) == 3.0
        assert proj.get_stat_std(StatCategory.REBOUNDS) == 2.0

        # Combo stat should use Pythagorean sum
        pra_std = proj.get_stat_std(StatCategory.PTS_REB_AST)
        expected = (3.0**2 + 2.0**2 + 1.5**2) ** 0.5
        assert pra_std == pytest.approx(expected)


class TestTeamContext:
    """Test TeamContext model."""

    def test_create_team_context(self) -> None:
        """Test TeamContext creation."""
        team = TeamContext(
            team_id="PHX",
            team_name="Phoenix Suns",
            pace=101.5,
            off_rating=118.2,
            def_rating=112.3,
            net_rating=5.9,
            is_home=True,
            is_back_to_back=False,
            rest_days=2,
        )

        assert team.team_id == "PHX"
        assert team.pace == 101.5
        assert team.is_home is True


class TestMatchupContext:
    """Test MatchupContext model."""

    def test_create_matchup(self) -> None:
        """Test MatchupContext creation."""
        home_team = TeamContext(
            team_id="PHX",
            team_name="Phoenix Suns",
            pace=101.5,
            off_rating=118.2,
            def_rating=112.3,
            net_rating=5.9,
            is_home=True,
        )

        away_team = TeamContext(
            team_id="LAL",
            team_name="Los Angeles Lakers",
            pace=99.8,
            off_rating=115.1,
            def_rating=113.2,
            net_rating=1.9,
            is_home=False,
        )

        matchup = MatchupContext(
            matchup_id="PHX_vs_LAL_20250124",
            league=League.NBA,
            game_date=datetime(2025, 1, 24, 19, 0),
            home_team=home_team,
            away_team=away_team,
            spread=-5.5,
            total=225.5,
        )

        assert matchup.matchup_id == "PHX_vs_LAL_20250124"
        assert matchup.spread == -5.5
        assert matchup.total == 225.5


class TestPropLine:
    """Test PropLine model."""

    def test_create_prop_line(self) -> None:
        """Test PropLine creation."""
        line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
            sportsbook="DraftKings",
        )

        assert line.line == 24.5
        assert line.stat == StatCategory.POINTS

    def test_implied_prob_negative_odds(self) -> None:
        """Test implied probability calculation for negative odds."""
        line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
        )

        # -110 odds -> 110/(110+100) = 0.5238
        over_prob = line.implied_prob(PropSide.OVER)
        assert over_prob == pytest.approx(0.5238, abs=0.001)

    def test_implied_prob_positive_odds(self) -> None:
        """Test implied probability calculation for positive odds."""
        line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=150,
            under_odds=-180,
        )

        # +150 odds -> 100/(150+100) = 0.4
        over_prob = line.implied_prob(PropSide.OVER)
        assert over_prob == pytest.approx(0.4, abs=0.001)

        # -180 odds -> 180/(180+100) = 0.6429
        under_prob = line.implied_prob(PropSide.UNDER)
        assert under_prob == pytest.approx(0.6429, abs=0.001)
