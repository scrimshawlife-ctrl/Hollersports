"""
Tests for NHL median-floor engine.

Validates determinism and correctness of projection calculations.
"""

import pytest
import numpy as np

from hollersports.nhl.types import FeatureSet
from hollersports.nhl.median_floor import compute_median_floor, assess_projection_quality


class TestComputeMedianFloor:
    """Test median-floor calculations."""

    @pytest.fixture
    def stable_features(self):
        """Create stable feature set for testing."""
        return FeatureSet(
            player_id="player1",
            game_id="game1",
            last5_sog_weighted=4.0,
            season_sog_median=3.5,
            last10_sog_list=[5, 4, 4, 3, 3, 3, 2, 4, 5, 3],
            toi_last5_median=18.0,
            toi_season_median=17.5,
        )

    def test_median_calculation(self, stable_features):
        """Test basic median calculation."""
        median, floor, sigma = compute_median_floor(stable_features)

        # Median should be weighted average: 0.6 * 4.0 + 0.4 * 3.5 = 3.8
        assert abs(median - 3.8) < 0.01

        # Floor should be <= median
        assert floor <= median

        # Sigma should be positive
        assert sigma > 0

    def test_floor_is_conservative(self, stable_features):
        """Floor should be at or below median."""
        median, floor, sigma = compute_median_floor(stable_features)
        assert floor <= median

    def test_determinism(self, stable_features):
        """Results should be deterministic."""
        result1 = compute_median_floor(stable_features)
        result2 = compute_median_floor(stable_features)

        assert result1 == result2

    def test_volatility_penalty(self):
        """High volatility should reduce projection."""
        volatile_features = FeatureSet(
            player_id="player1",
            game_id="game1",
            last5_sog_weighted=4.0,
            season_sog_median=4.0,
            last10_sog_list=[8, 1, 7, 2, 6, 1, 7, 2, 6, 1],  # Very volatile
            toi_last5_median=18.0,
            toi_season_median=17.5,
        )

        median, floor, sigma = compute_median_floor(volatile_features)

        # With high volatility and low floor, should apply penalty
        # Exact value depends on config, but should be < baseline
        assert sigma > 2.0  # Should detect high std


class TestAssessProjectionQuality:
    """Test projection quality assessment."""

    def test_over_with_safe_floor(self):
        """Over with floor above line should score high."""
        quality, reasons = assess_projection_quality(
            median=5.0,
            floor=4.5,
            line=4.0,
            side="HIGHER",
        )

        assert quality > 0.7
        assert any("above line" in r.lower() for r in reasons)

    def test_over_with_risky_floor(self):
        """Over with floor below line should score lower."""
        quality, reasons = assess_projection_quality(
            median=5.0,
            floor=3.0,
            line=4.0,
            side="HIGHER",
        )

        assert quality < 0.7
        assert any("below line" in r.lower() for r in reasons)

    def test_under_with_safe_floor(self):
        """Under with floor well below line should score high."""
        quality, reasons = assess_projection_quality(
            median=3.0,
            floor=2.0,
            line=4.0,
            side="LOWER",
        )

        assert quality > 0.7
        assert any("below line" in r.lower() for r in reasons)

    def test_quality_bounds(self):
        """Quality should be clamped to [0, 1]."""
        quality, _ = assess_projection_quality(
            median=10.0,
            floor=9.0,
            line=2.0,
            side="HIGHER",
        )

        assert 0.0 <= quality <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
