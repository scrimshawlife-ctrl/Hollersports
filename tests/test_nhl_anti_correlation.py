"""
Tests for NHL anti-correlation architecture.

Validates leg pairing rules and correlation checks.
"""

import pytest

from hollersports.nhl.types import SOGProjection, Side, NHLGameRow
from hollersports.nhl.anti_correlation import check_leg_compatibility, build_anti_correlated_slate


class TestLegCompatibility:
    """Test leg compatibility checks."""

    @pytest.fixture
    def sample_data(self):
        """Create sample dataset."""
        return [
            NHLGameRow(
                game_id="game1",
                date="2024-01-01",
                team="BOS",
                opponent="TOR",
                is_home=1,
                player_id="player1",
                player_name="Player One",
                position="F",
                toi_minutes=18.0,
                sog=4,
            ),
            NHLGameRow(
                game_id="game1",
                date="2024-01-01",
                team="BOS",
                opponent="TOR",
                is_home=1,
                player_id="player2",
                player_name="Player Two",
                position="F",
                toi_minutes=17.0,
                sog=3,
            ),
            NHLGameRow(
                game_id="game1",
                date="2024-01-01",
                team="TOR",
                opponent="BOS",
                is_home=0,
                player_id="player3",
                player_name="Player Three",
                position="F",
                toi_minutes=19.0,
                sog=5,
            ),
        ]

    def test_same_player_incompatible(self, sample_data):
        """Same player should be incompatible."""
        proj1 = SOGProjection(
            player_id="player1",
            player_name="Player One",
            game_id="game1",
            mu=4.0,
            sigma=1.5,
            median=4.0,
            floor=3.0,
            p_hit=0.65,
            confidence=0.70,
            line=3.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="abc123",
        )

        proj2 = SOGProjection(
            player_id="player1",  # Same player
            player_name="Player One",
            game_id="game1",
            mu=4.0,
            sigma=1.5,
            median=4.0,
            floor=3.0,
            p_hit=0.60,
            confidence=0.65,
            line=4.5,
            side=Side.LOWER,
            reasons=[],
            flags=[],
            provenance_hash="def456",
        )

        compatible, reason = check_leg_compatibility(proj1, proj2, sample_data)

        assert compatible is False
        assert "same player" in reason.lower()

    def test_same_team_both_overs_incompatible(self, sample_data):
        """Same team, both overs should be incompatible."""
        proj1 = SOGProjection(
            player_id="player1",
            player_name="Player One",
            game_id="game1",
            mu=4.0,
            sigma=1.5,
            median=4.0,
            floor=3.0,
            p_hit=0.65,
            confidence=0.70,
            line=3.5,
            side=Side.HIGHER,  # Over
            reasons=[],
            flags=[],
            provenance_hash="abc123",
        )

        proj2 = SOGProjection(
            player_id="player2",
            player_name="Player Two",
            game_id="game1",
            mu=3.5,
            sigma=1.5,
            median=3.5,
            floor=2.5,
            p_hit=0.60,
            confidence=0.65,
            line=3.0,
            side=Side.HIGHER,  # Also over
            reasons=[],
            flags=[],
            provenance_hash="def456",
        )

        compatible, reason = check_leg_compatibility(proj1, proj2, sample_data)

        assert compatible is False
        assert "both overs" in reason.lower()

    def test_different_teams_compatible(self, sample_data):
        """Different teams should be compatible."""
        proj1 = SOGProjection(
            player_id="player1",
            player_name="Player One",
            game_id="game1",
            mu=4.0,
            sigma=1.5,
            median=4.0,
            floor=3.0,
            p_hit=0.65,
            confidence=0.70,
            line=3.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="abc123",
        )

        proj3 = SOGProjection(
            player_id="player3",
            player_name="Player Three",
            game_id="game1",
            mu=5.0,
            sigma=1.5,
            median=5.0,
            floor=4.0,
            p_hit=0.70,
            confidence=0.75,
            line=4.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="ghi789",
        )

        compatible, reason = check_leg_compatibility(proj1, proj3, sample_data)

        assert compatible is True
        assert "different teams" in reason.lower()

    def test_different_games_compatible(self):
        """Different games should always be compatible."""
        proj1 = SOGProjection(
            player_id="player1",
            player_name="Player One",
            game_id="game1",
            mu=4.0,
            sigma=1.5,
            median=4.0,
            floor=3.0,
            p_hit=0.65,
            confidence=0.70,
            line=3.5,
            side=Side.HIGHER,
            reasons=[],
            flags=[],
            provenance_hash="abc123",
        )

        proj2 = SOGProjection(
            player_id="player2",
            player_name="Player Two",
            game_id="game2",  # Different game
            mu=3.5,
            sigma=1.5,
            median=3.5,
            floor=2.5,
            p_hit=0.60,
            confidence=0.65,
            line=3.0,
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
            SOGProjection(
                player_id=f"player{i}",
                player_name=f"Player {i}",
                game_id=f"game{i}",
                mu=4.0,
                sigma=1.5,
                median=4.0,
                floor=3.0,
                p_hit=0.70 - i * 0.05,  # Descending quality
                confidence=0.75 - i * 0.05,
                line=3.5,
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
