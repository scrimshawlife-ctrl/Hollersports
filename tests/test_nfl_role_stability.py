"""
Tests for NFL position-specific role stability gates.

Validates WR/TE/RB/QB stability checks.
"""

import pytest
from hollersports.nfl.types import FeatureSet, Market
from hollersports.nfl.role_stability import check_role_stability


class TestWRStability:
    """Test WR role stability gates."""

    def test_stable_wr_passes(self):
        """Stable WR with high routes and target share should pass."""
        features = FeatureSet(
            player_id="wr1",
            game_id="game1",
            position="WR",
            last5_targets=[6, 7, 6, 8, 7],
            last5_receptions=[4, 5, 4, 6, 5],
            last5_routes=[25, 26, 24, 27, 26],
            last5_snaps=[55, 58, 56, 59, 57],
            last5_rush_att=[0, 0, 0, 0, 0],
            season_targets_median=7.0,
            season_receptions_median=5.0,
            season_routes_median=25.0,
            season_snaps_median=56.0,
            target_share_proxy=0.20,  # High share
            route_participation=0.85,
            rush_share=0.0,
            snap_share=0.70,  # High snap share
            role_stable=True,
            volatility_flag=False,
        )

        config = {
            "wr_min_routes": 20,
            "wr_min_target_share": 0.15,
            "wr_min_snap_share": 0.50,
            "min_role_score": 0.60,
        }

        result = check_role_stability(features, Market.RECEPTIONS, config)

        assert result.passed
        assert result.role_score >= 0.60

    def test_low_routes_wr_fails(self):
        """WR with low routes should fail."""
        features = FeatureSet(
            player_id="wr1",
            game_id="game1",
            position="WR",
            last5_targets=[3, 2, 3, 2, 3],
            last5_receptions=[2, 1, 2, 1, 2],
            last5_routes=[12, 10, 11, 9, 10],  # Low routes
            last5_snaps=[20, 18, 19, 17, 18],
            last5_rush_att=[0, 0, 0, 0, 0],
            season_targets_median=3.0,
            season_receptions_median=2.0,
            season_routes_median=10.0,
            season_snaps_median=18.0,
            target_share_proxy=0.08,  # Low share
            route_participation=0.55,
            rush_share=0.0,
            snap_share=0.25,  # Low snap share
            role_stable=False,
            volatility_flag=False,
        )

        config = {
            "wr_min_routes": 20,
            "wr_min_target_share": 0.15,
            "wr_min_snap_share": 0.50,
            "min_role_score": 0.60,
        }

        result = check_role_stability(features, Market.RECEPTIONS, config)

        assert not result.passed
        assert "wr_routes_low" in " ".join(result.flags)


class TestTEStability:
    """Test TE role stability gates."""

    def test_stable_te_passes(self):
        """Stable TE with sufficient routes and target share should pass."""
        features = FeatureSet(
            player_id="te1",
            game_id="game1",
            position="TE",
            last5_targets=[5, 6, 5, 6, 5],
            last5_receptions=[4, 4, 3, 5, 4],
            last5_routes=[18, 19, 17, 20, 18],
            last5_snaps=[48, 50, 47, 51, 49],
            last5_rush_att=[0, 0, 0, 0, 0],
            season_targets_median=5.0,
            season_receptions_median=4.0,
            season_routes_median=18.0,
            season_snaps_median=49.0,
            target_share_proxy=0.14,  # Above TE threshold
            route_participation=0.70,
            rush_share=0.0,
            snap_share=0.60,
            role_stable=True,
            volatility_flag=False,
        )

        config = {
            "te_min_routes": 15,
            "te_min_target_share": 0.12,
            "te_min_snap_share": 0.45,
            "min_role_score": 0.60,
        }

        result = check_role_stability(features, Market.RECEPTIONS, config)

        assert result.passed


class TestRBStability:
    """Test RB role stability gates."""

    def test_rushing_rb_passes(self):
        """RB with high rush share should pass."""
        features = FeatureSet(
            player_id="rb1",
            game_id="game1",
            position="RB",
            last5_targets=[2, 3, 2, 2, 3],
            last5_receptions=[2, 2, 1, 2, 2],
            last5_routes=[10, 12, 9, 11, 10],
            last5_snaps=[35, 38, 36, 37, 36],
            last5_rush_att=[15, 16, 14, 17, 15],
            season_targets_median=2.0,
            season_receptions_median=2.0,
            season_routes_median=10.0,
            season_snaps_median=36.0,
            target_share_proxy=0.06,  # Low
            route_participation=0.30,
            rush_share=0.45,  # High rush share
            snap_share=0.55,
            role_stable=True,
            volatility_flag=False,
        )

        config = {
            "rb_min_snap_share": 0.40,
            "rb_min_rush_share": 0.25,
            "rb_min_target_share": 0.10,
            "min_role_score": 0.60,
        }

        result = check_role_stability(features, Market.RUSH_ATT, config)

        assert result.passed

    def test_passing_rb_passes(self):
        """RB with high target share (passing role) should pass."""
        features = FeatureSet(
            player_id="rb1",
            game_id="game1",
            position="RB",
            last5_targets=[6, 7, 6, 7, 6],
            last5_receptions=[5, 6, 5, 6, 5],
            last5_routes=[22, 24, 23, 25, 23],
            last5_snaps=[40, 42, 41, 43, 41],
            last5_rush_att=[8, 9, 8, 9, 8],
            season_targets_median=6.0,
            season_receptions_median=5.0,
            season_routes_median=23.0,
            season_snaps_median=41.0,
            target_share_proxy=0.15,  # High target share
            route_participation=0.55,
            rush_share=0.20,  # Below threshold
            snap_share=0.60,
            role_stable=True,
            volatility_flag=False,
        )

        config = {
            "rb_min_snap_share": 0.40,
            "rb_min_rush_share": 0.25,
            "rb_min_target_share": 0.10,
            "min_role_score": 0.60,
        }

        result = check_role_stability(features, Market.RECEPTIONS, config)

        assert result.passed


class TestQBStability:
    """Test QB role stability gates."""

    def test_starter_qb_passes(self):
        """Starting QB (high snap share) should pass."""
        features = FeatureSet(
            player_id="qb1",
            game_id="game1",
            position="QB",
            last5_targets=[0, 0, 0, 0, 0],
            last5_receptions=[0, 0, 0, 0, 0],
            last5_routes=[0, 0, 0, 0, 0],
            last5_snaps=[65, 66, 64, 67, 65],
            last5_rush_att=[3, 4, 3, 3, 4],
            season_targets_median=0.0,
            season_receptions_median=0.0,
            season_routes_median=0.0,
            season_snaps_median=65.0,
            target_share_proxy=0.0,
            route_participation=0.0,
            rush_share=0.0,
            snap_share=0.98,  # Starter
            role_stable=True,
            volatility_flag=False,
        )

        config = {
            "qb_min_snap_share": 0.95,
            "min_role_score": 0.60,
        }

        result = check_role_stability(features, Market.PASS_ATT, config)

        assert result.passed

    def test_backup_qb_fails(self):
        """Backup QB (low snap share) should fail."""
        features = FeatureSet(
            player_id="qb2",
            game_id="game1",
            position="QB",
            last5_targets=[0, 0, 0, 0, 0],
            last5_receptions=[0, 0, 0, 0, 0],
            last5_routes=[0, 0, 0, 0, 0],
            last5_snaps=[5, 3, 4, 2, 3],
            last5_rush_att=[1, 0, 1, 0, 0],
            season_targets_median=0.0,
            season_receptions_median=0.0,
            season_routes_median=0.0,
            season_snaps_median=3.0,
            target_share_proxy=0.0,
            route_participation=0.0,
            rush_share=0.0,
            snap_share=0.05,  # Backup
            role_stable=False,
            volatility_flag=False,
        )

        config = {
            "qb_min_snap_share": 0.95,
            "min_role_score": 0.60,
        }

        result = check_role_stability(features, Market.PASS_ATT, config)

        assert not result.passed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
