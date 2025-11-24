"""
Unit tests for configuration system.

Tests SEED enforcement, provenance tracking, and config loading.
"""

import pytest

from hollersports.core.config import Settings, get_settings, reset_settings


class TestSettings:
    """Test Settings model and factory."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def test_default_settings(self) -> None:
        """Test that default settings load correctly."""
        settings = Settings()

        assert settings.seed == 42
        assert settings.log_level == "INFO"
        assert settings.venue.enabled is True
        assert settings.roles.enabled is True
        assert settings.scripts.enabled is True

    def test_settings_compute_hash(self) -> None:
        """Test that settings hash is deterministic."""
        settings1 = Settings(seed=42)
        settings2 = Settings(seed=42)

        hash1 = settings1.compute_hash()
        hash2 = settings2.compute_hash()

        assert hash1 == hash2
        assert len(hash1) == 16  # First 16 chars of SHA256

    def test_settings_hash_changes_with_config(self) -> None:
        """Test that hash changes when config changes."""
        settings1 = Settings(seed=42)
        settings2 = Settings(seed=99)

        assert settings1.compute_hash() != settings2.compute_hash()

    def test_create_provenance(self) -> None:
        """Test provenance metadata creation."""
        settings = Settings(seed=42)
        provenance = settings.create_provenance()

        assert provenance.seed == 42
        assert provenance.version == "0.1.0"
        assert provenance.config_hash == settings.compute_hash()
        assert provenance.timestamp is not None

    def test_get_settings_singleton(self) -> None:
        """Test that get_settings returns singleton."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_get_settings_reload(self) -> None:
        """Test that get_settings can reload."""
        settings1 = get_settings()
        settings2 = get_settings(reload=True)

        # Should be new instance
        assert settings1 is not settings2

    def test_venue_settings(self) -> None:
        """Test VenueSettings nested model."""
        settings = Settings()

        assert settings.venue.arenas_data_path == "config/arenas.json"
        assert settings.venue.default_pace_modifier == 1.0
        assert settings.venue.altitude_threshold_m == 1000

    def test_role_settings(self) -> None:
        """Test RoleSettings nested model."""
        settings = Settings()

        assert settings.roles.min_games_for_inference == 5
        assert settings.roles.usage_hinge_threshold == 28.0
        assert settings.roles.glass_cleaner_trb_threshold == 18.0

    def test_script_settings(self) -> None:
        """Test ScriptSettings nested model."""
        settings = Settings()

        assert settings.scripts.num_scripts_per_matchup == 5
        assert settings.scripts.fragility_high_threshold == 0.6
        assert settings.scripts.fragility_low_threshold == 0.25

    def test_parlay_settings_modes(self) -> None:
        """Test ParlaySettings for all three modes."""
        settings = Settings()

        # Conservative
        assert settings.parlays.conservative_max_fragility == 0.3
        assert settings.parlays.conservative_min_ev == 0.05

        # Balanced
        assert settings.parlays.balanced_max_fragility == 0.5
        assert settings.parlays.balanced_min_ev == 0.03

        # Aggressive
        assert settings.parlays.aggressive_max_fragility == 0.75
        assert settings.parlays.aggressive_min_ev == 0.01

    def test_settings_override_from_dict(self) -> None:
        """Test that settings can be overridden via dict."""
        custom_config = {"seed": 999, "log_level": "DEBUG", "venue": {"enabled": False}}

        settings = Settings(**custom_config)

        assert settings.seed == 999
        assert settings.log_level == "DEBUG"
        assert settings.venue.enabled is False
