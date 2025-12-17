# FILE: HollerSports/tests/test_state_isolation.py
# Tests demonstrating proper state isolation and no slate leakage.

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.reset_state import (
    init_new_slate_state,
    assert_state_matches_inputs,
    hard_reset_runtime_artifacts,
    make_market_key,
    merge_calibration_delta,
    CalibrationMemory,
)
from engine.slate_runner import SlateRunner


class TestStateIsolation(unittest.TestCase):
    """Test that state properly isolates slates and prevents leakage."""

    def setUp(self):
        """Set up test fixtures."""
        self.games_payload_slate1 = {
            "games": [
                {
                    "game_id": "NBA_20251217_LAL_BOS",
                    "home_team": "BOS",
                    "away_team": "LAL",
                    "venue": "home",
                }
            ]
        }

        self.lines_payload_slate1 = {
            make_market_key("NBA", "NBA_20251217_LAL_BOS", "player_123", "PTS", 25.5, "OVER"): {
                "sport": "NBA",
                "game_id": "NBA_20251217_LAL_BOS",
                "player_id": "player_123",
                "player_name": "LeBron James",
                "market": "PTS",
                "line": 25.5,
            }
        }

        self.games_payload_slate2 = {
            "games": [
                {
                    "game_id": "NBA_20251218_GSW_MIA",
                    "home_team": "MIA",
                    "away_team": "GSW",
                    "venue": "home",
                }
            ]
        }

        self.lines_payload_slate2 = {
            make_market_key("NBA", "NBA_20251218_GSW_MIA", "player_456", "PTS", 28.5, "OVER"): {
                "sport": "NBA",
                "game_id": "NBA_20251218_GSW_MIA",
                "player_id": "player_456",
                "player_name": "Stephen Curry",
                "market": "PTS",
                "line": 28.5,
            }
        }

    def test_fresh_state_no_carryover(self):
        """Test that fresh state has no artifacts from previous runs."""
        state = init_new_slate_state(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        self.assertEqual(len(state.picks), 0)
        self.assertEqual(len(state.simulations), 0)
        self.assertEqual(len(state.game_context.by_game_id), 0)
        self.assertEqual(len(state.calibration.adjustments), 0)

    def test_different_slates_different_fingerprints(self):
        """Test that different slates have different source fingerprints."""
        state1 = init_new_slate_state(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        state2 = init_new_slate_state(
            slate_id="NBA_2025-12-18_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate2,
            lines_payload=self.lines_payload_slate2,
        )

        self.assertNotEqual(state1.slate.source_fingerprint, state2.slate.source_fingerprint)
        self.assertNotEqual(state1.market.fingerprint, state2.market.fingerprint)

    def test_assert_state_matches_inputs_success(self):
        """Test that validation passes when inputs match state."""
        state = init_new_slate_state(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        # Should not raise
        assert_state_matches_inputs(
            state,
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
            provider="PrizePicks",
        )

    def test_assert_state_matches_inputs_failure(self):
        """Test that validation fails when inputs don't match state."""
        state = init_new_slate_state(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        # Should raise RuntimeError
        with self.assertRaises(RuntimeError) as ctx:
            assert_state_matches_inputs(
                state,
                games_payload=self.games_payload_slate2,  # Different games!
                lines_payload=self.lines_payload_slate2,  # Different lines!
                provider="PrizePicks",
            )

        self.assertIn("slate state mismatch", str(ctx.exception).lower())

    def test_hard_reset_clears_artifacts(self):
        """Test that hard reset clears computed artifacts."""
        state = init_new_slate_state(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        # Add some artifacts
        state.picks.append({"test": "pick"})
        state.simulations["test_key"] = {"test": "sim"}
        state.game_context.by_game_id["test_game"] = {"test": "context"}

        self.assertEqual(len(state.picks), 1)
        self.assertEqual(len(state.simulations), 1)
        self.assertEqual(len(state.game_context.by_game_id), 1)

        # Reset
        hard_reset_runtime_artifacts(state)

        self.assertEqual(len(state.picks), 0)
        self.assertEqual(len(state.simulations), 0)
        self.assertEqual(len(state.game_context.by_game_id), 0)

    def test_calibration_memory_controlled_merge(self):
        """Test that calibration memory merges correctly when opted-in."""
        prior_calibration = CalibrationMemory(enabled=True)
        prior_calibration.adjustments = {
            "NBA:player:123": {"PTS_mean_delta": 1.5, "PTS_std_multiplier": 0.9}
        }
        prior_calibration.recompute_fingerprint()

        state = init_new_slate_state(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
            keep_calibration_memory=True,
            prior_calibration=prior_calibration,
        )

        self.assertTrue(state.calibration.enabled)
        self.assertIn("NBA:player:123", state.calibration.adjustments)
        self.assertEqual(state.calibration.adjustments["NBA:player:123"]["PTS_mean_delta"], 1.5)

    def test_calibration_memory_discard_by_default(self):
        """Test that calibration memory is discarded by default."""
        prior_calibration = CalibrationMemory(enabled=True)
        prior_calibration.adjustments = {
            "NBA:player:123": {"PTS_mean_delta": 1.5}
        }

        state = init_new_slate_state(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
            keep_calibration_memory=False,  # Explicit
            prior_calibration=prior_calibration,
        )

        self.assertEqual(len(state.calibration.adjustments), 0)

    def test_slate_runner_integration(self):
        """Test SlateRunner properly initializes and validates state."""
        runner = SlateRunner(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        # Validation should pass
        runner.validate_inputs()

        # State should be clean
        self.assertEqual(len(runner.state.picks), 0)
        self.assertEqual(len(runner.state.simulations), 0)

    def test_slate_runner_compute_game_context(self):
        """Test that game context is properly computed and scoped."""
        runner = SlateRunner(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        runner.compute_game_context()

        # Should have context for our game
        self.assertIn("NBA_20251217_LAL_BOS", runner.state.game_context.by_game_id)
        self.assertNotEqual(runner.state.game_context.fingerprint, "")

    def test_multiple_slates_no_leakage(self):
        """Test that processing multiple slates doesn't leak state."""
        runner1 = SlateRunner(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        runner1.compute_game_context()
        runner1.state.picks.append({"test": "pick1"})

        runner2 = SlateRunner(
            slate_id="NBA_2025-12-18_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate2,
            lines_payload=self.lines_payload_slate2,
        )

        # Runner2 should have clean state
        self.assertEqual(len(runner2.state.picks), 0)
        self.assertEqual(len(runner2.state.simulations), 0)
        self.assertNotIn("NBA_20251217_LAL_BOS", runner2.state.game_context.by_game_id)

        # Runner1 should still have its state
        self.assertEqual(len(runner1.state.picks), 1)

    def test_provenance_tracking(self):
        """Test that provenance is properly tracked."""
        state = init_new_slate_state(
            slate_id="NBA_2025-12-17_EVENING",
            sport="NBA",
            provider="PrizePicks",
            games_payload=self.games_payload_slate1,
            lines_payload=self.lines_payload_slate1,
        )

        self.assertIn("reset_policy", state.provenance)
        self.assertIn("inputs", state.provenance)
        self.assertIn("created_utc_epoch", state.provenance)
        self.assertTrue(state.provenance["reset_policy"]["no_slate_bleed"])

    def test_market_key_determinism(self):
        """Test that market keys are deterministic and stable."""
        key1 = make_market_key("NBA", "game_123", "player_456", "PTS", 25.5, "OVER")
        key2 = make_market_key("NBA", "game_123", "player_456", "PTS", 25.5, "OVER")
        key3 = make_market_key("NBA", "game_123", "player_456", "PTS", 25.5, "UNDER")

        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)

    def test_calibration_merge_delta(self):
        """Test controlled calibration delta merging."""
        base = CalibrationMemory(enabled=True)
        base.adjustments = {
            "NBA:player:123": {"PTS_mean_delta": 1.0, "AST_mean_delta": 0.5}
        }
        base.recompute_fingerprint()

        delta = {
            "NBA:player:123": {"PTS_mean_delta": 1.5},  # Update existing
            "NBA:player:456": {"PTS_mean_delta": 0.8},  # Add new
        }

        merged = merge_calibration_delta(base, delta, allow_new_keys=True)

        self.assertEqual(merged.adjustments["NBA:player:123"]["PTS_mean_delta"], 1.5)
        self.assertEqual(merged.adjustments["NBA:player:123"]["AST_mean_delta"], 0.5)  # Preserved
        self.assertIn("NBA:player:456", merged.adjustments)


if __name__ == "__main__":
    unittest.main()
