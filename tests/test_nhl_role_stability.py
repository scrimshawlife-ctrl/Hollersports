"""
Tests for NHL role stability filter.

Validates TOI and PP stability gates.
"""

import pytest

from hollersports.nhl.types import FeatureSet
from hollersports.nhl.role_stability import check_role_stability


class TestRoleStability:
    """Test role stability filter."""

    def test_passes_with_stable_toi(self):
        """Stable TOI should pass."""
        features = FeatureSet(
            player_id="player1",
            game_id="game1",
            last5_sog_weighted=4.0,
            season_sog_median=3.5,
            last10_sog_list=[4, 4, 3, 3, 3],
            toi_last5_median=18.0,
            toi_season_median=17.5,  # Within 15% of last5
        )

        result = check_role_stability(features)

        assert result.passed is True
        assert result.toi_stable is True
        assert result.role_score > 0.5

    def test_rejects_low_toi(self):
        """Low season TOI should reject."""
        features = FeatureSet(
            player_id="player1",
            game_id="game1",
            last5_sog_weighted=4.0,
            season_sog_median=3.5,
            last10_sog_list=[4, 4, 3, 3, 3],
            toi_last5_median=12.0,
            toi_season_median=11.5,  # Below 14.0 threshold
        )

        result = check_role_stability(features)

        assert result.passed is False
        assert any("Low TOI" in f for f in result.flags)

    def test_rejects_unstable_toi(self):
        """Unstable TOI (large change) should reject."""
        features = FeatureSet(
            player_id="player1",
            game_id="game1",
            last5_sog_weighted=4.0,
            season_sog_median=3.5,
            last10_sog_list=[4, 4, 3, 3, 3],
            toi_last5_median=20.0,
            toi_season_median=15.0,  # 33% increase - beyond 15% threshold
        )

        result = check_role_stability(features)

        assert result.passed is False
        assert any("unstable" in f.lower() for f in result.flags)

    def test_pp_stability_bonus(self):
        """Stable PP usage should boost score."""
        stable_pp = FeatureSet(
            player_id="player1",
            game_id="game1",
            last5_sog_weighted=4.0,
            season_sog_median=3.5,
            last10_sog_list=[4, 4, 3, 3, 3],
            toi_last5_median=18.0,
            toi_season_median=17.5,
            pp_share=0.25,
            pp_share_last5=0.24,  # Stable
        )

        result_with_pp = check_role_stability(stable_pp)

        assert result_with_pp.passed is True
        assert result_with_pp.pp_stable is True
        assert result_with_pp.role_score >= 0.9  # Should get full bonus

    def test_missing_pp_no_penalty(self):
        """Missing PP data should not penalize."""
        no_pp = FeatureSet(
            player_id="player1",
            game_id="game1",
            last5_sog_weighted=4.0,
            season_sog_median=3.5,
            last10_sog_list=[4, 4, 3, 3, 3],
            toi_last5_median=18.0,
            toi_season_median=17.5,
            pp_share=None,
            pp_share_last5=None,
        )

        result = check_role_stability(no_pp)

        assert result.passed is True
        # Should still get partial score without PP data
        assert result.role_score >= 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
