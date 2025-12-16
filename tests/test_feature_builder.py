"""
Tests for feature_builder module.

Validates deterministic hashing, feature extraction, and key generation.
"""

import pytest

from hollersports.calibration.venue_coach_adjustments.models import (
    PropRecord,
    GameContext,
    PropMarket,
    PropSide,
)
from hollersports.calibration.venue_coach_adjustments.feature_builder import (
    stable_hash_to_bucket,
    bucket_timezone,
    build_features,
    make_correction_key,
)


class TestStableHashing:
    """Test deterministic categorical hashing."""

    def test_hash_determinism(self):
        """Same input should always hash to same bucket."""
        venue = "TD_Garden"
        bucket1 = stable_hash_to_bucket(venue, 100, "venue")
        bucket2 = stable_hash_to_bucket(venue, 100, "venue")
        assert bucket1 == bucket2

    def test_hash_different_salts(self):
        """Different salts should produce different buckets."""
        venue = "TD_Garden"
        bucket1 = stable_hash_to_bucket(venue, 100, "venue")
        bucket2 = stable_hash_to_bucket(venue, 100, "coach")
        # Very likely to be different (not guaranteed but >99.99%)
        assert bucket1 != bucket2

    def test_hash_in_range(self):
        """Hash should always be in valid bucket range."""
        for value in ["TD_Garden", "Staples_Center", "MSG", "Oracle_Arena"]:
            bucket = stable_hash_to_bucket(value, 100, "venue")
            assert 0 <= bucket < 100

    def test_hash_distribution(self):
        """Hashes should distribute reasonably across buckets."""
        venues = [f"Venue_{i}" for i in range(200)]
        buckets = [stable_hash_to_bucket(v, 100, "venue") for v in venues]

        # Check that we use at least 50% of buckets (probabilistically sound)
        unique_buckets = len(set(buckets))
        assert unique_buckets >= 50


class TestTimezoneBucketing:
    """Test timezone bucketing logic."""

    def test_bucket_none(self):
        """None should bucket to 0."""
        assert bucket_timezone(None) == 0

    def test_bucket_zero(self):
        """Zero should bucket to 0."""
        assert bucket_timezone(0) == 0

    def test_bucket_west_coast(self):
        """West coast (-3 hours) should bucket to -2."""
        assert bucket_timezone(-3) == -2
        assert bucket_timezone(-4) == -2

    def test_bucket_east_coast(self):
        """East coast (+3 hours) should bucket to 2."""
        assert bucket_timezone(3) == 2
        assert bucket_timezone(4) == 2

    def test_bucket_small_delta(self):
        """Small deltas should bucket to -1, 0, or 1."""
        assert bucket_timezone(-2) == -1
        assert bucket_timezone(-1) == -1
        assert bucket_timezone(1) == 1
        assert bucket_timezone(2) == 1


class TestBuildFeatures:
    """Test feature building from records and contexts."""

    @pytest.fixture
    def sample_record(self):
        """Create sample PropRecord for testing."""
        return PropRecord(
            player_id="player123",
            game_id="game456",
            market=PropMarket.PTS,
            line=25.5,
            actual=28.0,
            side=PropSide.HIGHER,
            timestamp="2024-01-15T19:00:00Z",
            team_id="BOS",
            opp_id="LAL",
            venue_id="TD_Garden",
        )

    @pytest.fixture
    def sample_context(self):
        """Create sample GameContext for testing."""
        return GameContext(
            venue_id="TD_Garden",
            is_home=True,
            team_id="BOS",
            opp_id="LAL",
            travel_b2b=False,
            travel_distance_km=4500.0,
            timezone_delta=-3,
            rest_days=2,
            coach_id="coach_stevens",
            rotation_depth_proxy=0.7,
            pace_proxy=102.5,
            opponent_defense_proxy=108.2,
            scheme_proxy="iso_heavy",
        )

    def test_basic_feature_extraction(self, sample_record, sample_context):
        """Test basic feature extraction."""
        features = build_features(sample_record, sample_context)

        assert features["market"] == "PTS"
        assert features["is_home"] == 1
        assert features["travel_b2b"] == 0
        assert features["timezone_bucket"] == -2
        assert features["rest_days"] == 2
        assert 0 <= features["venue_bucket"] < 100
        assert 0 <= features["coach_bucket"] < 50

    def test_missing_optional_fields(self, sample_record):
        """Test handling of missing optional fields."""
        minimal_context = GameContext(
            venue_id="TD_Garden",
            is_home=True,
            team_id="BOS",
            opp_id="LAL",
        )

        features = build_features(sample_record, minimal_context)

        assert features["coach_bucket"] == -1  # No coach
        assert features["scheme_bucket"] == -1  # No scheme
        assert features["rest_days"] == 1  # Default
        assert features["travel_distance_km"] == 0.0  # Default

    def test_determinism(self, sample_record, sample_context):
        """Features should be deterministic."""
        features1 = build_features(sample_record, sample_context)
        features2 = build_features(sample_record, sample_context)

        assert features1 == features2


class TestMakeCorrectionKey:
    """Test correction key generation."""

    @pytest.fixture
    def sample_features(self):
        """Sample feature dict."""
        return {
            "market": "PTS",
            "venue_bucket": 42,
            "coach_bucket": 7,
            "is_home": 1,
            "travel_b2b": 0,
            "timezone_bucket": -2,
        }

    def test_full_key(self, sample_features):
        """Test full key with all features."""
        key = make_correction_key(sample_features)
        assert key == ("PTS", 42, 7, 1, 0, -2)

    def test_no_coach(self, sample_features):
        """Test key without coach."""
        key = make_correction_key(sample_features, include_coach=False)
        assert key == ("PTS", 42, -1, 1, 0, -2)

    def test_no_timezone(self, sample_features):
        """Test key without timezone."""
        key = make_correction_key(sample_features, include_timezone=False)
        assert key == ("PTS", 42, 7, 1, 0, 0)

    def test_minimal_key(self, sample_features):
        """Test minimal key (no coach, no timezone)."""
        key = make_correction_key(
            sample_features,
            include_coach=False,
            include_timezone=False,
        )
        assert key == ("PTS", 42, -1, 1, 0, 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
