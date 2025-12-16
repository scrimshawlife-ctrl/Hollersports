"""
Tests for NFL position-aware anti-correlation architecture.

Validates leg pairing rules and correlation checks.
"""

import pytest
from hollersports.nfl.types import Projection, NFLGameRow, Side, Market
from hollersports.nfl.anti_correlation import check_leg_compatibility, build_anti_correlated_slate


class TestLegCompatibility:
    """Test leg compatibility checks."""

    @pytest.fixture
    def sample_data(self):
        """Create sample dataset."""
        return [
            NFLGameRow(
                game_id="game1",
                date="2024-09-08",
                team="KC",
                opponent="DET",
                is_home=1,
                player_id="player1",
                player_name="Player One",
                position="WR",
                snaps=55,
                targets=8,
                receptions=6,
                receiving_yards=75.0,
                rushing_attempts=0,
                rushing_yards=0.0,
            ),
            NFLGameRow(
                game_id="game1",
                date="2024-09-08",
                team="KC",
                opponent="DET",
                is_home=1,
                player_id="player2",
                player_name="Player Two",
                position="TE",
                snaps=48,
                targets=6,
                receptions=5,
                receiving_yards=60.0,
                rushing_attempts=0,
                rushing_yards=0.0,
            ),
            NFLGameRow(
                game_id="game1",
                date="2024-09-08",
                team="DET",
                opponent="KC",
                is_home=0,
                player_id="player3",
                player_name="Player Three",
                position="RB",
                snaps=45,
                targets=4,
                receptions=3,
                receiving_yards=25.0,
                rushing_attempts=18,
                rushing_yards=85.0,
            ),
        ]

    def test_same_player_incompatible(self, sample_data):
        """Same player should be incompatible."""
        proj1 = Projection(
            player_id="player1",
            player_name="Player One",
            position="WR",
            game_id="game1",
            market=Market.RECEPTIONS,
            mu=6.0,
            sigma=2.0,
            median=6.0,
            floor=4.5,
            script_mus={"NEUTRAL": 6.0},
            script_priors={"NEUTRAL": 1.0},
            p_hit=0.65,
            confidence=0.70,
            line=5.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="abc123",
        )

        proj2 = Projection(
            player_id="player1",  # Same player
            player_name="Player One",
            position="WR",
            game_id="game1",
            market=Market.REC_YDS,
            mu=75.0,
            sigma=20.0,
            median=75.0,
            floor=60.0,
            script_mus={"NEUTRAL": 75.0},
            script_priors={"NEUTRAL": 1.0},
            p_hit=0.60,
            confidence=0.65,
            line=70.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="def456",
        )

        compatible, reason = check_leg_compatibility(proj1, proj2, sample_data)

        assert compatible is False
        assert "same player" in reason.lower()

    def test_same_team_both_overs_incompatible(self, sample_data):
        """Same team, both overs on volume markets should be incompatible."""
        proj1 = Projection(
            player_id="player1",
            player_name="Player One",
            position="WR",
            game_id="game1",
            market=Market.RECEPTIONS,
            mu=6.0,
            sigma=2.0,
            median=6.0,
            floor=4.5,
            script_mus={"NEUTRAL": 6.0},
            script_priors={"NEUTRAL": 1.0},
            p_hit=0.65,
            confidence=0.70,
            line=5.5,
            side=Side.HIGHER,  # Over
            reasons=[],
            flags=[],
            provenance_hash="abc123",
        )

        proj2 = Projection(
            player_id="player2",
            player_name="Player Two",
            position="TE",
            game_id="game1",
            market=Market.TARGETS,
            mu=6.5,
            sigma=2.0,
            median=6.5,
            floor=5.0,
            script_mus={"NEUTRAL": 6.5},
            script_priors={"NEUTRAL": 1.0},
            p_hit=0.60,
            confidence=0.65,
            line=6.0,
            side=Side.HIGHER,  # Also over
            reasons=[],
            flags=[],
            provenance_hash="def456",
        )

        compatible, reason = check_leg_compatibility(proj1, proj2, sample_data)

        assert compatible is False
        assert "correlated volume" in reason.lower() or "both overs" in reason.lower()

    def test_opposing_teams_compatible(self, sample_data):
        """Opposing teams should be compatible."""
        proj1 = Projection(
            player_id="player1",
            player_name="Player One",
            position="WR",
            game_id="game1",
            market=Market.RECEPTIONS,
            mu=6.0,
            sigma=2.0,
            median=6.0,
            floor=4.5,
            script_mus={"NEUTRAL": 6.0},
            script_priors={"NEUTRAL": 1.0},
            p_hit=0.65,
            confidence=0.70,
            line=5.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="abc123",
        )

        proj3 = Projection(
            player_id="player3",
            player_name="Player Three",
            position="RB",
            game_id="game1",
            market=Market.RUSH_ATT,
            mu=18.0,
            sigma=4.0,
            median=18.0,
            floor=15.0,
            script_mus={"NEUTRAL": 18.0},
            script_priors={"NEUTRAL": 1.0},
            p_hit=0.70,
            confidence=0.75,
            line=16.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="ghi789",
        )

        compatible, reason = check_leg_compatibility(proj1, proj3, sample_data)

        assert compatible is True
        assert "opposing teams" in reason.lower() or "different teams" in reason.lower()

    def test_different_games_compatible(self):
        """Different games should always be compatible."""
        proj1 = Projection(
            player_id="player1",
            player_name="Player One",
            position="WR",
            game_id="game1",
            market=Market.RECEPTIONS,
            mu=6.0,
            sigma=2.0,
            median=6.0,
            floor=4.5,
            script_mus={"NEUTRAL": 6.0},
            script_priors={"NEUTRAL": 1.0},
            p_hit=0.65,
            confidence=0.70,
            line=5.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="abc123",
        )

        proj2 = Projection(
            player_id="player2",
            player_name="Player Two",
            position="TE",
            game_id="game2",  # Different game
            market=Market.RECEPTIONS,
            mu=5.0,
            sigma=2.0,
            median=5.0,
            floor=3.5,
            script_mus={"NEUTRAL": 5.0},
            script_priors={"NEUTRAL": 1.0},
            p_hit=0.60,
            confidence=0.65,
            line=4.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="def456",
        )

        compatible, reason = check_leg_compatibility(proj1, proj2, [])

        assert compatible is True
        assert "different games" in reason.lower()


class TestBuildAntiCorrelatedSlate:
    """Test anti-correlated slate building."""

    def test_builds_slate_without_conflicts(self):
        """Should build slate avoiding conflicts."""
        # Create test candidates (all different games for simplicity)
        candidates = [
            Projection(
                player_id=f"player{i}",
                player_name=f"Player {i}",
                position="WR",
                game_id=f"game{i}",
                market=Market.RECEPTIONS,
                mu=6.0,
                sigma=2.0,
                median=6.0,
                floor=4.5,
                script_mus={"NEUTRAL": 6.0},
                script_priors={"NEUTRAL": 1.0},
                p_hit=0.75 - i * 0.05,  # Descending quality
                confidence=0.80 - i * 0.05,
                line=5.5,
                side=Side.HIGHER,
                reasons=[],
                flags=[],
                provenance_hash=f"hash{i}",
            )
            for i in range(10)
        ]

        slate = build_anti_correlated_slate(candidates, [], target_size=5)

        assert len(slate) == 5
        # Should be top 5 by quality (since all different games)
        assert slate[0].player_id == "player0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
