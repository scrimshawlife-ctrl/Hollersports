"""
Unit tests for RolePriorityTagger.

Tests role inference heuristics, confidence scoring, and edge cases.
"""

import pytest

from hollersports.core.config import Settings
from hollersports.core.models import PlayerStats
from hollersports.roles import PlayerRole, RoleTag, RolePriorityTagger


class TestPlayerRole:
    """Test PlayerRole enum."""

    def test_role_values(self) -> None:
        """Test role enum values."""
        assert PlayerRole.USAGE_HINGE.value == "usage_hinge"
        assert PlayerRole.GLASS_CLEANER.value == "glass_cleaner"
        assert PlayerRole.CONNECTOR.value == "connector"


class TestRoleTag:
    """Test RoleTag model."""

    def test_create_role_tag(self) -> None:
        """Test basic RoleTag creation."""
        tag = RoleTag(
            role=PlayerRole.USAGE_HINGE,
            confidence=0.85,
            notes={"usg_pct": 30.5, "ast_pct": 20.2},
        )

        assert tag.role == PlayerRole.USAGE_HINGE
        assert tag.confidence == 0.85
        assert tag.notes["usg_pct"] == 30.5

    def test_role_tag_immutable(self) -> None:
        """Test that RoleTag is frozen."""
        tag = RoleTag(role=PlayerRole.CONNECTOR, confidence=0.75)

        with pytest.raises(Exception):  # Pydantic ValidationError
            tag.confidence = 0.9  # type: ignore

    def test_get_display_label(self) -> None:
        """Test display label formatting."""
        tag = RoleTag(role=PlayerRole.GLASS_CLEANER, confidence=0.72)

        label = tag.get_display_label()
        assert "glass_cleaner" in label
        assert "0.72" in label

    def test_is_high_confidence(self) -> None:
        """Test high confidence detection."""
        high = RoleTag(role=PlayerRole.USAGE_HINGE, confidence=0.85)
        medium = RoleTag(role=PlayerRole.CONNECTOR, confidence=0.65)
        low = RoleTag(role=PlayerRole.UNKNOWN, confidence=0.3)

        assert high.is_high_confidence(threshold=0.7) is True
        assert medium.is_high_confidence(threshold=0.7) is False
        assert low.is_high_confidence(threshold=0.7) is False

    def test_is_scorer_role(self) -> None:
        """Test scorer role detection."""
        scorer = RoleTag(role=PlayerRole.USAGE_HINGE, confidence=0.8)
        tunnel = RoleTag(role=PlayerRole.TUNNEL_SCORER, confidence=0.7)
        connector = RoleTag(role=PlayerRole.CONNECTOR, confidence=0.75)

        assert scorer.is_scorer_role() is True
        assert tunnel.is_scorer_role() is True
        assert connector.is_scorer_role() is False

    def test_is_facilitator_role(self) -> None:
        """Test facilitator role detection."""
        connector = RoleTag(role=PlayerRole.CONNECTOR, confidence=0.75)
        playmaker = RoleTag(role=PlayerRole.PRIMARY_PLAYMAKER, confidence=0.85)
        scorer = RoleTag(role=PlayerRole.USAGE_HINGE, confidence=0.8)

        assert connector.is_facilitator_role() is True
        assert playmaker.is_facilitator_role() is True
        assert scorer.is_facilitator_role() is False

    def test_is_specialist_role(self) -> None:
        """Test specialist role detection."""
        glass = RoleTag(role=PlayerRole.GLASS_CLEANER, confidence=0.8)
        three_d = RoleTag(role=PlayerRole.THREE_AND_D, confidence=0.65)
        scorer = RoleTag(role=PlayerRole.USAGE_HINGE, confidence=0.8)

        assert glass.is_specialist_role() is True
        assert three_d.is_specialist_role() is True
        assert scorer.is_specialist_role() is False


class TestRolePriorityTagger:
    """Test RolePriorityTagger."""

    def test_init(self) -> None:
        """Test tagger initialization."""
        tagger = RolePriorityTagger()
        assert tagger.settings is not None

    def test_infer_usage_hinge(self) -> None:
        """Test inferring usage_hinge role."""
        tagger = RolePriorityTagger()

        # High usage, moderate assists (Devin Booker type)
        stats = PlayerStats(
            player_id="booker123",
            player_name="Devin Booker",
            team="PHX",
            games_played=10,
            min_per_game=35.0,
            pts_per_game=27.5,
            reb_per_game=4.5,
            ast_per_game=6.8,
            stl_per_game=0.9,
            blk_per_game=0.3,
            tov_per_game=2.8,
            fg3m_per_game=2.8,
            usage_pct=30.5,
            ast_pct=22.0,
            reb_pct=8.5,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.USAGE_HINGE
        assert role_tag.confidence > 0.7
        assert role_tag.notes["usg_pct"] == 30.5

    def test_infer_primary_playmaker(self) -> None:
        """Test inferring primary_playmaker role."""
        tagger = RolePriorityTagger()

        # High usage + high assists (Luka Doncic type)
        stats = PlayerStats(
            player_id="luka123",
            player_name="Luka Doncic",
            team="DAL",
            games_played=12,
            min_per_game=37.0,
            pts_per_game=28.5,
            reb_per_game=8.3,
            ast_per_game=8.7,
            stl_per_game=1.4,
            blk_per_game=0.5,
            tov_per_game=3.2,
            fg3m_per_game=3.1,
            usage_pct=32.0,
            ast_pct=38.5,
            reb_pct=14.2,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.PRIMARY_PLAYMAKER
        assert role_tag.confidence > 0.7

    def test_infer_glass_cleaner(self) -> None:
        """Test inferring glass_cleaner role."""
        tagger = RolePriorityTagger()

        # High rebounds, low usage (Clint Capela type)
        stats = PlayerStats(
            player_id="capela123",
            player_name="Clint Capela",
            team="ATL",
            games_played=10,
            min_per_game=30.0,
            pts_per_game=11.2,
            reb_per_game=11.8,
            ast_per_game=1.2,
            stl_per_game=0.8,
            blk_per_game=1.8,
            tov_per_game=1.1,
            fg3m_per_game=0.0,
            usage_pct=15.5,
            ast_pct=5.2,
            reb_pct=22.5,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.GLASS_CLEANER
        assert role_tag.confidence > 0.7

    def test_infer_connector(self) -> None:
        """Test inferring connector role."""
        tagger = RolePriorityTagger()

        # Moderate usage, high assists (Draymond Green type)
        stats = PlayerStats(
            player_id="dray123",
            player_name="Draymond Green",
            team="GSW",
            games_played=11,
            min_per_game=32.0,
            pts_per_game=8.5,
            reb_per_game=7.2,
            ast_per_game=6.8,
            stl_per_game=0.9,
            blk_per_game=0.8,
            tov_per_game=2.3,
            fg3m_per_game=0.8,
            usage_pct=18.5,
            ast_pct=28.5,
            reb_pct=13.2,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.CONNECTOR
        assert role_tag.confidence > 0.6

    def test_infer_tunnel_scorer(self) -> None:
        """Test inferring tunnel_scorer role."""
        tagger = RolePriorityTagger()

        # Moderate-high usage, low assists (Jordan Clarkson type)
        stats = PlayerStats(
            player_id="clarkson123",
            player_name="Jordan Clarkson",
            team="UTA",
            games_played=10,
            min_per_game=26.0,
            pts_per_game=18.5,
            reb_per_game=3.2,
            ast_per_game=2.5,
            stl_per_game=0.7,
            blk_per_game=0.2,
            tov_per_game=1.8,
            fg3m_per_game=3.2,
            usage_pct=25.0,
            ast_pct=10.5,
            reb_pct=6.8,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.TUNNEL_SCORER
        assert role_tag.confidence > 0.6

    def test_infer_three_and_d(self) -> None:
        """Test inferring three_and_d role."""
        tagger = RolePriorityTagger()

        # Low usage, good 3P volume
        stats = PlayerStats(
            player_id="player123",
            player_name="3&D Specialist",
            team="MIA",
            games_played=10,
            min_per_game=28.0,
            pts_per_game=10.5,
            reb_per_game=3.8,
            ast_per_game=1.8,
            stl_per_game=1.2,
            blk_per_game=0.4,
            tov_per_game=0.9,
            fg3m_per_game=2.5,
            usage_pct=15.0,
            ast_pct=8.5,
            reb_pct=7.2,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.THREE_AND_D
        assert role_tag.confidence > 0.5

    def test_infer_bench_microwave(self) -> None:
        """Test inferring bench_microwave role."""
        tagger = RolePriorityTagger()

        # Good scoring, limited minutes
        stats = PlayerStats(
            player_id="player123",
            player_name="Bench Scorer",
            team="PHX",
            games_played=10,
            min_per_game=22.0,
            pts_per_game=14.5,
            reb_per_game=2.5,
            ast_per_game=2.2,
            stl_per_game=0.6,
            blk_per_game=0.2,
            tov_per_game=1.5,
            fg3m_per_game=1.8,
            usage_pct=24.5,
            ast_pct=12.0,
            reb_pct=6.0,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.BENCH_MICROWAVE
        assert role_tag.confidence > 0.6

    def test_infer_rim_protector(self) -> None:
        """Test inferring rim_protector role."""
        tagger = RolePriorityTagger()

        # High blocks, low usage
        stats = PlayerStats(
            player_id="player123",
            player_name="Shot Blocker",
            team="UTA",
            games_played=10,
            min_per_game=28.0,
            pts_per_game=9.5,
            reb_per_game=8.2,
            ast_per_game=1.1,
            stl_per_game=0.5,
            blk_per_game=2.3,
            tov_per_game=1.2,
            fg3m_per_game=0.1,
            usage_pct=14.5,
            ast_pct=4.2,
            reb_pct=16.5,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.RIM_PROTECTOR
        assert role_tag.confidence > 0.6

    def test_infer_all_around(self) -> None:
        """Test inferring all_around role."""
        tagger = RolePriorityTagger()

        # Balanced profile (Khris Middleton type)
        stats = PlayerStats(
            player_id="player123",
            player_name="All-Around Player",
            team="MIL",
            games_played=10,
            min_per_game=32.0,
            pts_per_game=18.5,
            reb_per_game=6.2,
            ast_per_game=5.1,
            stl_per_game=0.9,
            blk_per_game=0.4,
            tov_per_game=2.0,
            fg3m_per_game=2.2,
            usage_pct=22.5,
            ast_pct=18.5,
            reb_pct=11.2,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.ALL_AROUND
        assert role_tag.confidence > 0.5

    def test_insufficient_games(self) -> None:
        """Test that insufficient games returns UNKNOWN."""
        tagger = RolePriorityTagger()

        # Only 3 games (below min of 5)
        stats = PlayerStats(
            player_id="player123",
            player_name="New Player",
            team="PHX",
            games_played=3,
            min_per_game=25.0,
            pts_per_game=20.0,
            reb_per_game=5.0,
            ast_per_game=4.0,
            stl_per_game=1.0,
            blk_per_game=0.5,
            tov_per_game=2.0,
            fg3m_per_game=2.0,
            usage_pct=28.0,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.UNKNOWN
        assert role_tag.confidence == 0.0

    def test_confidence_adjustment_for_games(self) -> None:
        """Test that confidence is adjusted based on games played."""
        tagger = RolePriorityTagger()

        # Create two identical stat profiles with different games played
        stats_few_games = PlayerStats(
            player_id="player1",
            player_name="Player 1",
            team="PHX",
            games_played=6,  # Just above minimum
            min_per_game=35.0,
            pts_per_game=27.0,
            reb_per_game=5.0,
            ast_per_game=6.0,
            stl_per_game=1.0,
            blk_per_game=0.5,
            tov_per_game=2.5,
            fg3m_per_game=2.5,
            usage_pct=30.0,
            ast_pct=22.0,
        )

        stats_many_games = PlayerStats(
            player_id="player2",
            player_name="Player 2",
            team="PHX",
            games_played=20,  # Well above minimum
            min_per_game=35.0,
            pts_per_game=27.0,
            reb_per_game=5.0,
            ast_per_game=6.0,
            stl_per_game=1.0,
            blk_per_game=0.5,
            tov_per_game=2.5,
            fg3m_per_game=2.5,
            usage_pct=30.0,
            ast_pct=22.0,
        )

        tag_few = tagger.infer_role(stats_few_games)
        tag_many = tagger.infer_role(stats_many_games)

        # Both should infer same role
        assert tag_few.role == tag_many.role

        # But more games should have higher confidence
        assert tag_many.confidence > tag_few.confidence

    def test_disabled_role_tagging(self) -> None:
        """Test that role tagging can be disabled."""
        settings = Settings(roles={"enabled": False})
        tagger = RolePriorityTagger(settings)

        stats = PlayerStats(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            games_played=10,
            min_per_game=35.0,
            pts_per_game=27.0,
            reb_per_game=5.0,
            ast_per_game=6.0,
            stl_per_game=1.0,
            blk_per_game=0.5,
            tov_per_game=2.5,
            fg3m_per_game=2.5,
            usage_pct=30.0,
        )

        role_tag = tagger.infer_role(stats)

        assert role_tag.role == PlayerRole.UNKNOWN
        assert role_tag.confidence == 0.0

    def test_tag_role_display(self) -> None:
        """Test display string generation."""
        tagger = RolePriorityTagger()

        high_conf = RoleTag(role=PlayerRole.USAGE_HINGE, confidence=0.85)
        medium_conf = RoleTag(role=PlayerRole.CONNECTOR, confidence=0.65)
        low_conf = RoleTag(role=PlayerRole.UNKNOWN, confidence=0.3)

        assert "high conf" in tagger.tag_role_display(high_conf)
        assert "medium" in tagger.tag_role_display(medium_conf)
        assert "low" in tagger.tag_role_display(low_conf)

    def test_get_role_impact_on_props(self) -> None:
        """Test getting role impact on prop categories."""
        tagger = RolePriorityTagger()

        usage_hinge = RoleTag(role=PlayerRole.USAGE_HINGE, confidence=0.85)
        glass_cleaner = RoleTag(role=PlayerRole.GLASS_CLEANER, confidence=0.80)

        usage_impact = tagger.get_role_impact_on_props(usage_hinge)
        glass_impact = tagger.get_role_impact_on_props(glass_cleaner)

        assert usage_impact["points"] == "high"
        assert usage_impact["assists"] == "medium"

        assert glass_impact["rebounds"] == "high"
        assert glass_impact["points"] == "low"

    def test_edge_case_borderline_thresholds(self) -> None:
        """Test players right at threshold boundaries."""
        tagger = RolePriorityTagger()

        # Exactly at usage_hinge threshold (28.0)
        stats = PlayerStats(
            player_id="player123",
            player_name="Borderline",
            team="PHX",
            games_played=10,
            min_per_game=35.0,
            pts_per_game=25.0,
            reb_per_game=5.0,
            ast_per_game=5.0,
            stl_per_game=1.0,
            blk_per_game=0.5,
            tov_per_game=2.5,
            fg3m_per_game=2.0,
            usage_pct=28.0,  # Exactly at threshold
            ast_pct=20.0,
        )

        role_tag = tagger.infer_role(stats)

        # Should classify as usage_hinge since >= threshold
        assert role_tag.role == PlayerRole.USAGE_HINGE
