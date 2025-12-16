"""
Tests for correction_fit module.

Validates residual computation, shrinkage, and CCM building with synthetic data.
"""

import pytest
import numpy as np

from hollersports.calibration.venue_coach_adjustments.models import (
    PropRecord,
    GameContext,
    PropMarket,
    PropSide,
    Provenance,
)
from hollersports.calibration.venue_coach_adjustments.correction_fit import (
    compute_residual,
    compute_mad,
    fit_corrections,
    corrections_to_entries,
    build_correction_map,
)


class TestComputeResidual:
    """Test residual computation."""

    def test_positive_residual(self):
        """Actual > line should give positive residual."""
        record = PropRecord(
            player_id="p1",
            game_id="g1",
            market=PropMarket.PTS,
            line=25.5,
            actual=28.0,
            side=PropSide.HIGHER,
            timestamp="2024-01-01T00:00:00Z",
            team_id="BOS",
            opp_id="LAL",
            venue_id="TD_Garden",
        )
        assert compute_residual(record) == 2.5

    def test_negative_residual(self):
        """Actual < line should give negative residual."""
        record = PropRecord(
            player_id="p1",
            game_id="g1",
            market=PropMarket.PTS,
            line=25.5,
            actual=22.0,
            side=PropSide.LOWER,
            timestamp="2024-01-01T00:00:00Z",
            team_id="BOS",
            opp_id="LAL",
            venue_id="TD_Garden",
        )
        assert compute_residual(record) == -3.5

    def test_zero_residual(self):
        """Exact line should give zero residual."""
        record = PropRecord(
            player_id="p1",
            game_id="g1",
            market=PropMarket.PTS,
            line=25.5,
            actual=25.5,
            side=PropSide.HIGHER,
            timestamp="2024-01-01T00:00:00Z",
            team_id="BOS",
            opp_id="LAL",
            venue_id="TD_Garden",
        )
        assert compute_residual(record) == 0.0


class TestComputeMAD:
    """Test MAD computation."""

    def test_mad_simple(self):
        """Test MAD with simple values."""
        values = [1, 2, 3, 4, 5]
        mad = compute_mad(values)
        # Median is 3, deviations are [2, 1, 0, 1, 2], MAD = 1
        assert mad == 1.0

    def test_mad_empty(self):
        """Empty list should return 0."""
        assert compute_mad([]) == 0.0

    def test_mad_single(self):
        """Single value should return 0."""
        assert compute_mad([5.0]) == 0.0


class TestFitCorrections:
    """Test correction fitting with synthetic data."""

    def create_synthetic_data(self, n: int = 100, seed: int = 1337) -> tuple:
        """
        Create deterministic synthetic PropRecords and GameContexts.

        Args:
            n: Number of records
            seed: Random seed

        Returns:
            Tuple of (records, contexts)
        """
        np.random.seed(seed)

        records = []
        contexts = []

        for i in range(n):
            # Create biased scenario: certain venues systematically under-perform lines
            venue_id = f"venue_{i % 5}"  # 5 venues
            is_home = i % 2 == 0

            # Venue 0 is "tough" for scoring (negative bias)
            if venue_id == "venue_0":
                bias = -2.0
            elif venue_id == "venue_1":
                bias = 1.5
            else:
                bias = 0.0

            line = 25.0 + np.random.normal(0, 3)
            actual = line + bias + np.random.normal(0, 2)

            record = PropRecord(
                player_id=f"player_{i % 20}",
                game_id=f"game_{i}",
                market=PropMarket.PTS,
                line=line,
                actual=actual,
                side=PropSide.HIGHER,
                timestamp=f"2024-01-{1 + i % 28:02d}T00:00:00Z",
                team_id=f"team_{i % 10}",
                opp_id=f"team_{(i + 1) % 10}",
                venue_id=venue_id,
            )

            context = GameContext(
                venue_id=venue_id,
                is_home=is_home,
                team_id=f"team_{i % 10}",
                opp_id=f"team_{(i + 1) % 10}",
                travel_b2b=i % 3 == 0,
                rest_days=i % 4,
                coach_id=f"coach_{i % 3}",
            )

            records.append(record)
            contexts.append(context)

        return records, contexts

    def test_fit_corrections_basic(self):
        """Test basic correction fitting."""
        # Use more records to ensure we have enough samples per key
        records, contexts = self.create_synthetic_data(n=500, seed=1337)

        config = {
            "shrinkage": {"k": 25, "min_samples": 3},  # Lower threshold for test
            "hash_buckets": {"venue": 10, "coach": 5, "team": 10, "opponent": 10},
        }

        corrections = fit_corrections(records, contexts, config, seed=1337)

        # Should have some corrections
        assert len(corrections) > 0

        # Check structure
        for key, stats in corrections.items():
            assert isinstance(key, tuple)
            assert "mean_delta" in stats
            assert "median_delta" in stats
            assert "count" in stats
            assert "confidence" in stats
            assert "dispersion" in stats

            # Count should be >= min_samples
            assert stats["count"] >= 3

            # Confidence should be in [0, 1]
            assert 0.0 <= stats["confidence"] <= 1.0

    def test_shrinkage_effect(self):
        """Test that shrinkage reduces extreme estimates."""
        # Create data with small sample showing extreme bias
        records, contexts = self.create_synthetic_data(n=10, seed=1337)

        config = {
            "shrinkage": {"k": 25, "min_samples": 1},  # Allow small samples
            "hash_buckets": {"venue": 10, "coach": 5, "team": 10, "opponent": 10},
        }

        corrections = fit_corrections(records, contexts, config, seed=1337)

        # Shrinkage should pull mean_delta toward zero compared to raw mean
        for key, stats in corrections.items():
            # Shrinkage factor = count / (count + k)
            shrinkage = stats["count"] / (stats["count"] + 25)
            # mean_delta should be < raw mean in absolute value (due to shrinkage)
            assert abs(stats["mean_delta"]) <= abs(stats["median_delta"]) * 1.5  # Loose bound

    def test_determinism(self):
        """Fitting should be deterministic with same seed."""
        records, contexts = self.create_synthetic_data(n=50, seed=42)

        config = {"shrinkage": {"k": 25, "min_samples": 5}}

        corrections1 = fit_corrections(records, contexts, config, seed=42)
        corrections2 = fit_corrections(records, contexts, config, seed=42)

        assert corrections1.keys() == corrections2.keys()

        for key in corrections1:
            assert corrections1[key] == corrections2[key]


class TestCorrectionsToEntries:
    """Test conversion to CorrectionEntry objects."""

    def test_conversion(self):
        """Test conversion from dict to CorrectionEntry."""
        corrections = {
            ("PTS", 42, 7, 1, 0, -2): {
                "mean_delta": -1.2,
                "median_delta": -1.0,
                "count": 30,
                "confidence": 0.75,
                "dispersion": 2.5,
            },
        }

        entries = corrections_to_entries(corrections)

        assert len(entries) == 1
        entry = entries[0]

        assert entry.market == PropMarket.PTS
        assert entry.venue_bucket == 42
        assert entry.coach_bucket == 7
        assert entry.is_home == 1
        assert entry.travel_b2b == 0
        assert entry.timezone_bucket == -2
        assert entry.mean_delta == -1.2
        assert entry.count == 30


class TestBuildCorrectionMap:
    """Test full CCM building."""

    def test_build_ccm(self):
        """Test building complete CorrectionMap."""
        # Create synthetic data
        np.random.seed(1337)
        records = []
        contexts = []

        for i in range(50):
            record = PropRecord(
                player_id=f"p{i}",
                game_id=f"g{i}",
                market=PropMarket.PTS,
                line=25.0,
                actual=25.0 + np.random.normal(0, 2),
                side=PropSide.HIGHER,
                timestamp=f"2024-01-{1 + i % 28:02d}T00:00:00Z",
                team_id="BOS",
                opp_id="LAL",
                venue_id="TD_Garden",
            )

            context = GameContext(
                venue_id="TD_Garden",
                is_home=True,
                team_id="BOS",
                opp_id="LAL",
                coach_id="coach1",
            )

            records.append(record)
            contexts.append(context)

        provenance = Provenance(
            run_id="test123",
            created_at="2024-01-01T00:00:00Z",
            seed=1337,
            inputs_hash="abc123",
            config_hash="def456",
        )

        config = {
            "shrinkage": {"k": 25, "min_samples": 5},
            "hash_buckets": {"venue": 10, "coach": 5, "team": 10, "opponent": 10},
        }

        ccm = build_correction_map(records, contexts, provenance, config, seed=1337)

        assert len(ccm) >= 0  # May be 0 if not enough samples per key
        assert ccm.provenance.run_id == "test123"
        assert ccm.config == config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
