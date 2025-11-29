"""
Unit tests for GameScriptSimulator.

Tests script enumeration, projection adjustments, and fragility calculation.
"""

from datetime import datetime

import pytest

from hollersports.core.config import Settings
from hollersports.core.models import MatchupContext, PlayerProjection, StatCategory, TeamContext
from hollersports.scripts import FragilityAnalysis, GameScript, GameScriptSimulator, ScriptProjection


class TestGameScript:
    """Test GameScript enum."""

    def test_script_values(self) -> None:
        """Test script enum values."""
        assert GameScript.PACE_UP.value == "pace_up"
        assert GameScript.SHOOTOUT.value == "shootout"
        assert GameScript.BALANCED.value == "balanced"


class TestScriptProjection:
    """Test ScriptProjection model."""

    def test_create_script_projection(self) -> None:
        """Test basic ScriptProjection creation."""
        proj = ScriptProjection(
            script=GameScript.PACE_UP,
            probability=0.35,
            proj_pts=26.5,
            proj_reb=6.2,
            proj_ast=4.8,
            std_dev=3.2,
        )

        assert proj.script == GameScript.PACE_UP
        assert proj.probability == 0.35
        assert proj.proj_pts == 26.5

    def test_script_projection_immutable(self) -> None:
        """Test that ScriptProjection is frozen."""
        proj = ScriptProjection(
            script=GameScript.BALANCED,
            probability=0.3,
            proj_pts=25.0,
            proj_reb=5.0,
            proj_ast=4.0,
            std_dev=3.0,
        )

        with pytest.raises(Exception):  # Pydantic ValidationError
            proj.probability = 0.5  # type: ignore

    def test_get_expected_value(self) -> None:
        """Test getting expected value for different stats."""
        proj = ScriptProjection(
            script=GameScript.SHOOTOUT,
            probability=0.25,
            proj_pts=28.5,
            proj_reb=6.0,
            proj_ast=5.5,
            std_dev=3.5,
        )

        assert proj.get_expected_value("pts") == 28.5
        assert proj.get_expected_value("reb") == 6.0
        assert proj.get_expected_value("ast") == 5.5


class TestFragilityAnalysis:
    """Test FragilityAnalysis model."""

    def test_create_fragility_analysis(self) -> None:
        """Test basic FragilityAnalysis creation."""
        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.4,
                proj_pts=25.0,
                proj_reb=5.0,
                proj_ast=4.0,
                std_dev=3.0,
                line=24.5,
                p_hit_line=0.55,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.3,
                proj_pts=27.0,
                proj_reb=5.5,
                proj_ast=4.5,
                std_dev=3.2,
                line=24.5,
                p_hit_line=0.75,
            ),
        ]

        analysis = FragilityAnalysis(
            scripts=scripts,
            fragility_index=0.3,
            dominant_script=GameScript.PACE_UP,
            script_diversity=0.85,
            weighted_mean=25.8,
            weighted_std=3.1,
        )

        assert analysis.fragility_index == 0.3
        assert analysis.dominant_script == GameScript.PACE_UP

    def test_get_script_hit_rate(self) -> None:
        """Test getting hit rate for specific script."""
        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.4,
                proj_pts=25.0,
                proj_reb=5.0,
                proj_ast=4.0,
                std_dev=3.0,
                line=24.5,
                p_hit_line=0.55,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.3,
                proj_pts=27.0,
                proj_reb=5.5,
                proj_ast=4.5,
                std_dev=3.2,
                line=24.5,
                p_hit_line=0.75,
            ),
        ]

        analysis = FragilityAnalysis(
            scripts=scripts,
            fragility_index=0.3,
            script_diversity=0.85,
            weighted_mean=25.8,
            weighted_std=3.1,
        )

        assert analysis.get_script_hit_rate(GameScript.BALANCED) == 0.55
        assert analysis.get_script_hit_rate(GameScript.PACE_UP) == 0.75
        assert analysis.get_script_hit_rate(GameScript.GRIND) is None

    def test_get_scripts_hitting(self) -> None:
        """Test getting list of scripts where line hits."""
        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.3,
                proj_pts=25.0,
                proj_reb=5.0,
                proj_ast=4.0,
                std_dev=3.0,
                line=24.5,
                p_hit_line=0.55,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.3,
                proj_pts=27.0,
                proj_reb=5.5,
                proj_ast=4.5,
                std_dev=3.2,
                line=24.5,
                p_hit_line=0.75,
            ),
            ScriptProjection(
                script=GameScript.GRIND,
                probability=0.4,
                proj_pts=22.0,
                proj_reb=4.5,
                proj_ast=3.5,
                std_dev=2.8,
                line=24.5,
                p_hit_line=0.30,
            ),
        ]

        analysis = FragilityAnalysis(
            scripts=scripts,
            fragility_index=0.5,
            script_diversity=0.9,
            weighted_mean=24.1,
            weighted_std=3.0,
        )

        hitting = analysis.get_scripts_hitting(threshold=0.5)
        assert GameScript.BALANCED in hitting
        assert GameScript.PACE_UP in hitting
        assert GameScript.GRIND not in hitting

    def test_is_fragile(self) -> None:
        """Test fragility detection."""
        fragile = FragilityAnalysis(
            scripts=[],
            fragility_index=0.75,
            script_diversity=0.3,
            weighted_mean=25.0,
            weighted_std=5.0,
        )

        robust = FragilityAnalysis(
            scripts=[],
            fragility_index=0.25,
            script_diversity=0.85,
            weighted_mean=25.0,
            weighted_std=2.0,
        )

        assert fragile.is_fragile(threshold=0.6) is True
        assert robust.is_fragile(threshold=0.6) is False

    def test_is_robust(self) -> None:
        """Test robustness detection."""
        fragile = FragilityAnalysis(
            scripts=[],
            fragility_index=0.75,
            script_diversity=0.3,
            weighted_mean=25.0,
            weighted_std=5.0,
        )

        robust = FragilityAnalysis(
            scripts=[],
            fragility_index=0.25,
            script_diversity=0.85,
            weighted_mean=25.0,
            weighted_std=2.0,
        )

        assert fragile.is_robust(threshold=0.3) is False
        assert robust.is_robust(threshold=0.3) is True


class TestGameScriptSimulator:
    """Test GameScriptSimulator."""

    def test_init(self) -> None:
        """Test simulator initialization."""
        sim = GameScriptSimulator()
        assert sim.settings is not None

    def test_simulate_scripts_high_pace(self) -> None:
        """Test script generation for high-pace matchup."""
        sim = GameScriptSimulator()

        # High pace teams
        home_team = TeamContext(
            team_id="SAC",
            team_name="Sacramento Kings",
            pace=104.0,
            off_rating=116.5,
            def_rating=113.2,
            net_rating=3.3,
            is_home=True,
        )

        away_team = TeamContext(
            team_id="GSW",
            team_name="Golden State Warriors",
            pace=102.5,
            off_rating=118.0,
            def_rating=112.0,
            net_rating=6.0,
            is_home=False,
        )

        matchup = MatchupContext(
            matchup_id="SAC_vs_GSW_20250124",
            league="nba",
            game_date=datetime(2025, 1, 24, 19, 0),
            home_team=home_team,
            away_team=away_team,
        )

        base_proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="SAC",
            matchup_id="SAC_vs_GSW_20250124",
            proj_min=35.0,
            proj_pts=25.0,
            proj_reb=5.0,
            proj_ast=4.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.0,
            proj_fg3m=2.5,
        )

        scripts = sim.simulate_scripts(matchup, base_proj)

        # Should include balanced and pace_up
        script_types = [s.script for s in scripts]
        assert GameScript.BALANCED in script_types
        assert GameScript.PACE_UP in script_types

        # Probabilities should sum to ~1.0
        total_prob = sum(s.probability for s in scripts)
        assert total_prob == pytest.approx(1.0, abs=0.01)

    def test_simulate_scripts_low_pace(self) -> None:
        """Test script generation for low-pace matchup."""
        sim = GameScriptSimulator()

        # Low pace teams (grind it out)
        home_team = TeamContext(
            team_id="MEM",
            team_name="Memphis Grizzlies",
            pace=97.5,
            off_rating=110.2,
            def_rating=108.5,
            net_rating=1.7,
            is_home=True,
        )

        away_team = TeamContext(
            team_id="SAS",
            team_name="San Antonio Spurs",
            pace=96.8,
            off_rating=109.5,
            def_rating=112.0,
            net_rating=-2.5,
            is_home=False,
        )

        matchup = MatchupContext(
            matchup_id="MEM_vs_SAS_20250124",
            league="nba",
            game_date=datetime(2025, 1, 24, 19, 0),
            home_team=home_team,
            away_team=away_team,
        )

        base_proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="MEM",
            matchup_id="MEM_vs_SAS_20250124",
            proj_min=35.0,
            proj_pts=22.0,
            proj_reb=6.0,
            proj_ast=3.5,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=1.8,
            proj_fg3m=1.5,
        )

        scripts = sim.simulate_scripts(matchup, base_proj)

        # Should include pace_down and/or grind
        script_types = [s.script for s in scripts]
        assert GameScript.PACE_DOWN in script_types or GameScript.GRIND in script_types

    def test_simulate_scripts_blowout_potential(self) -> None:
        """Test script generation for lopsided matchup."""
        sim = GameScriptSimulator()

        home_team = TeamContext(
            team_id="BOS",
            team_name="Boston Celtics",
            pace=100.0,
            off_rating=120.5,
            def_rating=110.0,
            net_rating=10.5,
            is_home=True,
        )

        away_team = TeamContext(
            team_id="DET",
            team_name="Detroit Pistons",
            pace=99.0,
            off_rating=108.0,
            def_rating=116.0,
            net_rating=-8.0,
            is_home=False,
        )

        # Large spread indicates blowout potential
        matchup = MatchupContext(
            matchup_id="BOS_vs_DET_20250124",
            league="nba",
            game_date=datetime(2025, 1, 24, 19, 0),
            home_team=home_team,
            away_team=away_team,
            spread=-10.5,
        )

        base_proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="BOS",
            matchup_id="BOS_vs_DET_20250124",
            proj_min=35.0,
            proj_pts=26.0,
            proj_reb=7.0,
            proj_ast=5.0,
            proj_stl=1.2,
            proj_blk=0.8,
            proj_tov=2.2,
            proj_fg3m=3.0,
        )

        scripts = sim.simulate_scripts(matchup, base_proj)

        # Should include blowout script
        script_types = [s.script for s in scripts]
        assert GameScript.BLOWOUT in script_types

    def test_evaluate_line_across_scripts(self) -> None:
        """Test evaluating a prop line across scripts."""
        sim = GameScriptSimulator()

        # Create some script projections
        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.4,
                proj_pts=25.0,
                proj_reb=5.0,
                proj_ast=4.0,
                std_dev=3.0,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.3,
                proj_pts=27.0,
                proj_reb=5.5,
                proj_ast=4.5,
                std_dev=3.2,
            ),
            ScriptProjection(
                script=GameScript.GRIND,
                probability=0.3,
                proj_pts=22.0,
                proj_reb=4.5,
                proj_ast=3.5,
                std_dev=2.8,
            ),
        ]

        # Evaluate line at 24.5 points
        evaluated = sim.evaluate_line_across_scripts(scripts, 24.5, StatCategory.POINTS)

        # All scripts should now have line and p_hit_line set
        for script_proj in evaluated:
            assert script_proj.line == 24.5
            assert script_proj.p_hit_line is not None

        # Pace_up should have highest hit probability
        pace_up = next(s for s in evaluated if s.script == GameScript.PACE_UP)
        grind = next(s for s in evaluated if s.script == GameScript.GRIND)

        assert pace_up.p_hit_line > grind.p_hit_line  # type: ignore

    def test_compute_fragility_low_fragility(self) -> None:
        """Test fragility calculation for robust prop (hits in multiple scripts)."""
        sim = GameScriptSimulator()

        # Prop that hits across multiple scripts
        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.3,
                proj_pts=26.0,
                proj_reb=5.0,
                proj_ast=4.0,
                std_dev=3.0,
                line=24.5,
                p_hit_line=0.65,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.3,
                proj_pts=27.5,
                proj_reb=5.5,
                proj_ast=4.5,
                std_dev=3.2,
                line=24.5,
                p_hit_line=0.78,
            ),
            ScriptProjection(
                script=GameScript.SHOOTOUT,
                probability=0.2,
                proj_pts=28.0,
                proj_reb=5.2,
                proj_ast=4.8,
                std_dev=3.5,
                line=24.5,
                p_hit_line=0.82,
            ),
            ScriptProjection(
                script=GameScript.GRIND,
                probability=0.2,
                proj_pts=23.5,
                proj_reb=4.8,
                proj_ast=3.5,
                std_dev=2.8,
                line=24.5,
                p_hit_line=0.48,
            ),
        ]

        analysis = sim.compute_fragility(scripts, line=24.5)

        # Should be low fragility (hits in multiple scripts)
        assert analysis.fragility_index < 0.5
        assert analysis.is_robust(threshold=0.5)

    def test_compute_fragility_high_fragility(self) -> None:
        """Test fragility calculation for fragile prop (only hits in one script)."""
        sim = GameScriptSimulator()

        # Prop that only hits in PACE_UP scenario
        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.4,
                proj_pts=24.0,
                proj_reb=5.0,
                proj_ast=4.0,
                std_dev=3.0,
                line=26.5,
                p_hit_line=0.30,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.2,
                proj_pts=28.0,
                proj_reb=5.5,
                proj_ast=4.5,
                std_dev=3.2,
                line=26.5,
                p_hit_line=0.85,
            ),
            ScriptProjection(
                script=GameScript.PACE_DOWN,
                probability=0.2,
                proj_pts=22.5,
                proj_reb=4.5,
                proj_ast=3.5,
                std_dev=2.8,
                line=26.5,
                p_hit_line=0.15,
            ),
            ScriptProjection(
                script=GameScript.GRIND,
                probability=0.2,
                proj_pts=21.0,
                proj_reb=4.2,
                proj_ast=3.2,
                std_dev=2.5,
                line=26.5,
                p_hit_line=0.08,
            ),
        ]

        analysis = sim.compute_fragility(scripts, line=26.5)

        # Should be high fragility (only hits in pace_up)
        assert analysis.fragility_index > 0.5
        assert analysis.is_fragile(threshold=0.5)
        assert analysis.dominant_script == GameScript.PACE_UP

    def test_disabled_script_simulation(self) -> None:
        """Test that script simulation can be disabled."""
        settings = Settings(scripts={"enabled": False})
        sim = GameScriptSimulator(settings)

        matchup = MatchupContext(
            matchup_id="TEST_20250124",
            league="nba",
            game_date=datetime(2025, 1, 24, 19, 0),
            home_team=TeamContext(
                team_id="PHX",
                team_name="Phoenix Suns",
                pace=102.0,
                off_rating=118.0,
                def_rating=112.0,
                net_rating=6.0,
                is_home=True,
            ),
            away_team=TeamContext(
                team_id="LAL",
                team_name="Los Angeles Lakers",
                pace=100.0,
                off_rating=115.0,
                def_rating=113.0,
                net_rating=2.0,
                is_home=False,
            ),
        )

        base_proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="PHX",
            matchup_id="TEST_20250124",
            proj_min=35.0,
            proj_pts=25.0,
            proj_reb=5.0,
            proj_ast=4.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.0,
            proj_fg3m=2.5,
        )

        scripts = sim.simulate_scripts(matchup, base_proj)

        # Should only return balanced script
        assert len(scripts) == 1
        assert scripts[0].script == GameScript.BALANCED
        assert scripts[0].probability == 1.0

    def test_back_to_back_favors_slow_pace(self) -> None:
        """Test that back-to-back games favor slower scripts."""
        sim = GameScriptSimulator()

        home_team = TeamContext(
            team_id="MIA",
            team_name="Miami Heat",
            pace=100.0,
            off_rating=115.0,
            def_rating=112.0,
            net_rating=3.0,
            is_home=True,
            is_back_to_back=True,  # Back-to-back game
        )

        away_team = TeamContext(
            team_id="ATL",
            team_name="Atlanta Hawks",
            pace=101.0,
            off_rating=114.0,
            def_rating=113.0,
            net_rating=1.0,
            is_home=False,
        )

        matchup = MatchupContext(
            matchup_id="MIA_vs_ATL_20250124",
            league="nba",
            game_date=datetime(2025, 1, 24, 19, 0),
            home_team=home_team,
            away_team=away_team,
        )

        base_proj = PlayerProjection(
            player_id="player123",
            player_name="Test Player",
            team="MIA",
            matchup_id="MIA_vs_ATL_20250124",
            proj_min=35.0,
            proj_pts=24.0,
            proj_reb=5.0,
            proj_ast=4.0,
            proj_stl=1.0,
            proj_blk=0.5,
            proj_tov=2.0,
            proj_fg3m=2.5,
        )

        scripts = sim.simulate_scripts(matchup, base_proj)

        # Should include PACE_DOWN
        script_types = [s.script for s in scripts]
        assert GameScript.PACE_DOWN in script_types

    def test_weighted_statistics(self) -> None:
        """Test that fragility analysis computes correct weighted stats."""
        sim = GameScriptSimulator()

        scripts = [
            ScriptProjection(
                script=GameScript.BALANCED,
                probability=0.5,
                proj_pts=25.0,
                proj_reb=5.0,
                proj_ast=4.0,
                std_dev=3.0,
            ),
            ScriptProjection(
                script=GameScript.PACE_UP,
                probability=0.5,
                proj_pts=27.0,
                proj_reb=5.5,
                proj_ast=4.5,
                std_dev=3.2,
            ),
        ]

        analysis = sim.compute_fragility(scripts)

        # Weighted mean should be (25*0.5 + 27*0.5) = 26.0
        assert analysis.weighted_mean == pytest.approx(26.0, abs=0.01)

        # Check that weighted_std is reasonable
        assert analysis.weighted_std > 0
