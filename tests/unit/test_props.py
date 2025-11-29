"""
Unit tests for PropRiskScorer.

Tests risk scoring integration, value calculation, and recommendation logic.
"""

import pytest

from hollersports.core.config import Settings
from hollersports.core.models import PlayerProjection, PropLine, StatCategory
from hollersports.props import PropRiskProfile, PropRiskScorer
from hollersports.roles.models import PlayerRole, RoleTag
from hollersports.scripts.models import FragilityAnalysis, GameScript, ScriptProjection
from hollersports.venue.models import VenueProfile


class TestPropRiskProfile:
    """Test PropRiskProfile model."""

    def test_create_prop_risk_profile(self) -> None:
        """Test basic PropRiskProfile creation."""
        profile = PropRiskProfile(
            player_id="player123",
            player_name="Test Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        assert profile.player_name == "Test Player"
        assert profile.line == 24.5
        assert profile.value_score == 0.08

    def test_is_plus_ev(self) -> None:
        """Test positive EV detection."""
        plus_ev = PropRiskProfile(
            player_id="player123",
            player_name="Test Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        minus_ev = PropRiskProfile(
            player_id="player456",
            player_name="Other Player",
            stat="points",
            line=24.5,
            value_score=0.01,
            volatility_score=0.4,
            fragility_index=0.3,
            recommended_side="avoid",
            confidence=0.3,
            projected_value=24.6,
            implied_prob_over=0.51,
            expected_value=0.1,
        )

        assert plus_ev.is_plus_ev(threshold=0.03) is True
        assert minus_ev.is_plus_ev(threshold=0.03) is False

    def test_is_high_risk(self) -> None:
        """Test high risk detection."""
        high_vol = PropRiskProfile(
            player_id="player123",
            player_name="Test Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.75,  # High volatility
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.6,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        high_frag = PropRiskProfile(
            player_id="player456",
            player_name="Other Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.75,  # High fragility
            recommended_side="higher",
            confidence=0.5,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        low_risk = PropRiskProfile(
            player_id="player789",
            player_name="Third Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.25,
            fragility_index=0.22,
            recommended_side="higher",
            confidence=0.85,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        assert high_vol.is_high_risk() is True
        assert high_frag.is_high_risk() is True
        assert low_risk.is_high_risk() is False

    def test_is_recommended(self) -> None:
        """Test recommendation detection."""
        recommended = PropRiskProfile(
            player_id="player123",
            player_name="Test Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        avoided = PropRiskProfile(
            player_id="player456",
            player_name="Other Player",
            stat="points",
            line=24.5,
            value_score=0.01,
            volatility_score=0.4,
            fragility_index=0.3,
            recommended_side="avoid",
            confidence=0.3,
            projected_value=24.6,
            implied_prob_over=0.51,
            expected_value=0.1,
        )

        assert recommended.is_recommended() is True
        assert avoided.is_recommended() is False

    def test_get_risk_level(self) -> None:
        """Test risk level categorization."""
        low = PropRiskProfile(
            player_id="player1",
            player_name="Low Risk",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.2,
            fragility_index=0.18,
            recommended_side="higher",
            confidence=0.85,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        medium = PropRiskProfile(
            player_id="player2",
            player_name="Medium Risk",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.4,
            fragility_index=0.45,
            recommended_side="higher",
            confidence=0.7,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        high = PropRiskProfile(
            player_id="player3",
            player_name="High Risk",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.7,
            fragility_index=0.65,
            recommended_side="higher",
            confidence=0.5,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        assert low.get_risk_level() == "low"
        assert medium.get_risk_level() == "medium"
        assert high.get_risk_level() == "high"

    def test_get_summary_string(self) -> None:
        """Test summary string generation."""
        profile = PropRiskProfile(
            player_id="player123",
            player_name="Devin Booker",
            stat="points",
            line=27.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=29.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        summary = profile.get_summary_string()

        assert "Devin Booker" in summary
        assert "points" in summary
        assert "HIGHER" in summary
        assert "27.5" in summary


class TestPropRiskScorer:
    """Test PropRiskScorer."""

    def test_init(self) -> None:
        """Test scorer initialization."""
        scorer = PropRiskScorer()
        assert scorer.settings is not None

    def test_score_prop_basic(self) -> None:
        """Test basic prop scoring without fragility analysis."""
        scorer = PropRiskScorer()

        projection = PlayerProjection(
            player_id="booker123",
            player_name="Devin Booker",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=27.0,
            proj_reb=5.0,
            proj_ast=6.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.5,
            proj_fg3m=3.0,
            pts_std=3.5,
        )

        prop_line = PropLine(
            player_id="booker123",
            player_name="Devin Booker",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
        )

        risk_profile = scorer.score_prop(projection, prop_line)

        assert risk_profile.player_name == "Devin Booker"
        assert risk_profile.line == 24.5
        assert risk_profile.stat == "points"
        assert risk_profile.projected_value > 24.5  # Should project over
        assert risk_profile.value_score > 0  # Positive EV

    def test_score_prop_with_venue(self) -> None:
        """Test prop scoring with venue context."""
        scorer = PropRiskScorer()

        projection = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="DEN",
            matchup_id="DEN_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=26.0,
            proj_reb=7.0,
            proj_ast=8.0,
            proj_stl=1.2,
            proj_blk=0.8,
            proj_tov=2.8,
            proj_fg3m=2.5,
            pts_std=3.2,
            venue_modifier=1.15,  # Denver boost
        )

        prop_line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="DEN_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
        )

        venue = VenueProfile(
            arena_id="DEN_BALL_ARENA",
            team="DEN",
            name="Ball Arena",
            city="Denver",
            altitude_m=1609,
            pace_modifier=1.05,
            three_point_modifier=1.03,
            rebound_modifier=1.02,
            home_edge_modifier=1.08,
            tags=["Altitude", "Pace+", "HomeEdge+"],
        )

        risk_profile = scorer.score_prop(projection, prop_line, venue_profile=venue)

        assert risk_profile.venue_profile is not None
        assert "Altitude" in risk_profile.venue_tags
        assert risk_profile.projected_value == 26.0

    def test_score_prop_with_role(self) -> None:
        """Test prop scoring with role context."""
        scorer = PropRiskScorer()

        projection = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
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
            pts_std=3.5,
        )

        prop_line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
        )

        role_tag = RoleTag(
            role=PlayerRole.USAGE_HINGE,
            confidence=0.85,
            notes={"usg_pct": 30.5, "ast_pct": 22.0},
        )

        risk_profile = scorer.score_prop(projection, prop_line, role_tag=role_tag)

        assert risk_profile.role_tag is not None
        assert risk_profile.role_tag.role == PlayerRole.USAGE_HINGE

    def test_score_prop_with_fragility(self) -> None:
        """Test prop scoring with fragility analysis."""
        scorer = PropRiskScorer()

        projection = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
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
            pts_std=3.5,
        )

        prop_line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
        )

        # Low fragility scenario (hits in multiple scripts)
        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.4,
                proj_pts=25.5,
                proj_reb=5.0,
                proj_ast=6.0,
                std_dev=3.2,
                line=24.5,
                p_hit_line=0.62,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.3,
                proj_pts=27.0,
                proj_reb=5.5,
                proj_ast=6.5,
                std_dev=3.5,
                line=24.5,
                p_hit_line=0.75,
            ),
            ScriptProjection(
                script=GameScript.SHOOTOUT,
                probability=0.3,
                proj_pts=28.0,
                proj_reb=5.2,
                proj_ast=6.8,
                std_dev=3.8,
                line=24.5,
                p_hit_line=0.82,
            ),
        ]

        fragility = FragilityAnalysis(
            scripts=scripts,
            fragility_index=0.25,  # Low fragility
            dominant_script=GameScript.SHOOTOUT,
            script_diversity=0.9,
            weighted_mean=26.5,
            weighted_std=3.4,
        )

        risk_profile = scorer.score_prop(projection, prop_line, fragility_analysis=fragility)

        assert risk_profile.fragility_analysis is not None
        assert risk_profile.fragility_index == 0.25
        assert risk_profile.projected_value == 26.5  # Uses weighted mean
        assert "robust" in risk_profile.risk_tags

    def test_high_fragility_recommend_avoid(self) -> None:
        """Test that high fragility props are avoided unless exceptional EV."""
        scorer = PropRiskScorer()

        projection = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=22.0,
            proj_pts=15.0,
            proj_reb=3.0,
            proj_ast=2.0,
            proj_stl=0.7,
            proj_blk=0.3,
            proj_tov=1.5,
            proj_fg3m=2.0,
            pts_std=4.0,
        )

        prop_line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=14.5,
            over_odds=-110,
            under_odds=-110,
        )

        # High fragility (only hits in one script)
        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.5,
                proj_pts=14.0,
                proj_reb=3.0,
                proj_ast=2.0,
                std_dev=3.8,
                line=14.5,
                p_hit_line=0.45,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.2,
                proj_pts=16.5,
                proj_reb=3.5,
                proj_ast=2.5,
                std_dev=4.2,
                line=14.5,
                p_hit_line=0.70,
            ),
            ScriptProjection(
                script=GameScript.PACE_DOWN,
                probability=0.3,
                proj_pts=13.0,
                proj_reb=2.8,
                proj_ast=1.8,
                std_dev=3.5,
                line=14.5,
                p_hit_line=0.35,
            ),
        ]

        fragility = FragilityAnalysis(
            scripts=scripts,
            fragility_index=0.75,  # High fragility
            dominant_script=GameScript.PACE_UP,
            script_diversity=0.4,
            weighted_mean=14.3,
            weighted_std=3.9,
        )

        risk_profile = scorer.score_prop(projection, prop_line, fragility_analysis=fragility)

        # Should recommend avoid due to high fragility and low EV
        assert risk_profile.recommended_side == "avoid"
        assert "fragile" in risk_profile.risk_tags

    def test_low_ev_recommend_avoid(self) -> None:
        """Test that low EV props are avoided."""
        settings = Settings(prop_risk={"min_ev_threshold": 0.03})
        scorer = PropRiskScorer(settings)

        projection = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=24.6,  # Just slightly over line
            proj_reb=5.0,
            proj_ast=6.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.5,
            proj_fg3m=3.0,
            pts_std=3.5,
        )

        prop_line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
        )

        risk_profile = scorer.score_prop(projection, prop_line)

        # Should recommend avoid due to low EV
        assert risk_profile.recommended_side == "avoid"
        assert "low_ev" in risk_profile.risk_tags

    def test_high_ev_confidence_boost(self) -> None:
        """Test that high EV boosts confidence."""
        scorer = PropRiskScorer()

        high_ev_projection = PlayerProjection(
            player_id="player1",
            player_name="High EV Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=29.0,  # Significantly over line
            proj_reb=5.0,
            proj_ast=6.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.5,
            proj_fg3m=3.0,
            pts_std=3.0,
        )

        moderate_ev_projection = PlayerProjection(
            player_id="player2",
            player_name="Moderate EV Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=26.0,
            proj_reb=5.0,
            proj_ast=6.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.5,
            proj_fg3m=3.0,
            pts_std=3.0,
        )

        prop_line = PropLine(
            player_id="player1",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
        )

        high_ev_profile = scorer.score_prop(high_ev_projection, prop_line)
        moderate_ev_profile = scorer.score_prop(moderate_ev_projection, prop_line)

        # High EV should have higher confidence
        assert high_ev_profile.confidence > moderate_ev_profile.confidence
        assert "strong_value" in high_ev_profile.risk_tags

    def test_under_recommendation(self) -> None:
        """Test that under is recommended when projection is below line."""
        scorer = PropRiskScorer()

        projection = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=35.0,
            proj_pts=22.0,  # Below line
            proj_reb=5.0,
            proj_ast=6.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.5,
            proj_fg3m=3.0,
            pts_std=3.0,
        )

        prop_line = PropLine(
            player_id="player123",
            player_name="Test Player",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=24.5,
            over_odds=-110,
            under_odds=-110,
        )

        risk_profile = scorer.score_prop(projection, prop_line)

        # Should recommend lower (under)
        assert risk_profile.recommended_side == "lower"
        assert risk_profile.value_score < 0  # Negative value score
        assert risk_profile.expected_value < 0  # Below line

    def test_volatility_from_role(self) -> None:
        """Test that certain roles increase volatility."""
        scorer = PropRiskScorer()

        projection = PlayerProjection(
            player_id="player123",
            player_name="Bench Scorer",
            team="PHX",
            matchup_id="PHX_vs_LAL_20250124",
            proj_min=22.0,
            proj_pts=14.0,
            proj_reb=2.5,
            proj_ast=1.8,
            proj_stl=0.6,
            proj_blk=0.2,
            proj_tov=1.2,
            proj_fg3m=2.2,
            pts_std=3.5,
        )

        prop_line = PropLine(
            player_id="player123",
            player_name="Bench Scorer",
            matchup_id="PHX_vs_LAL_20250124",
            stat=StatCategory.POINTS,
            line=12.5,
            over_odds=-110,
            under_odds=-110,
        )

        # Bench microwave role (high volatility)
        bench_role = RoleTag(
            role=PlayerRole.BENCH_MICROWAVE,
            confidence=0.7,
            notes={"usg_pct": 24.5, "min_per_game": 22.0},
        )

        risk_profile = scorer.score_prop(projection, prop_line, role_tag=bench_role)

        # Bench role should have higher volatility
        assert risk_profile.volatility_score > 0.4
