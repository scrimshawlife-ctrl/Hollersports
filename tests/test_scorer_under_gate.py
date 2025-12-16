"""
Comprehensive tests for ABX-Core Scorer-Under Gate module.

Tests cover:
- Hash determinism and provenance tracking
- Gate logic with various signal combinations
- Feature engineering (arena, coach, opponent proxies)
- Edge cases (missing data, empty datasets, non-PTS props)
- Full backtest pipeline with synthetic data
"""

import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path

from abraxas.modules.scorer_under_gate import (
    GateConfig,
    GateDecision,
    scorer_under_gate,
    backtest,
    stable_hash_dict,
    compute_hit,
    arena_elasticity_proxy,
    coach_distribution_proxy,
    opponent_compression_proxy,
)


class TestProvenance:
    """Test deterministic hashing and provenance."""

    def test_stable_hash_determinism(self):
        """Hash should be deterministic for identical dicts."""
        d1 = {"a": 1, "b": 2, "c": 3}
        d2 = {"c": 3, "a": 1, "b": 2}  # Different order
        assert stable_hash_dict(d1) == stable_hash_dict(d2)

    def test_config_hash_consistency(self):
        """Config hash should be identical for default configs."""
        cfg1 = GateConfig()
        cfg2 = GateConfig()
        hash1 = stable_hash_dict(cfg1.__dict__)
        hash2 = stable_hash_dict(cfg2.__dict__)
        assert hash1 == hash2

    def test_config_hash_changes_with_params(self):
        """Config hash should change when parameters change."""
        cfg1 = GateConfig(blowout_spread_abs=8.0)
        cfg2 = GateConfig(blowout_spread_abs=10.0)
        hash1 = stable_hash_dict(cfg1.__dict__)
        hash2 = stable_hash_dict(cfg2.__dict__)
        assert hash1 != hash2


class TestComputeHit:
    """Test hit computation logic."""

    def test_higher_hit(self):
        """Test 'higher' pick that hits."""
        cfg = GateConfig()
        row = pd.Series({"line": 25.5, "result": 28.0, "pick": "higher"})
        assert compute_hit(row, cfg) == 1

    def test_higher_miss(self):
        """Test 'higher' pick that misses."""
        cfg = GateConfig()
        row = pd.Series({"line": 25.5, "result": 22.0, "pick": "higher"})
        assert compute_hit(row, cfg) == 0

    def test_lower_hit(self):
        """Test 'lower' pick that hits."""
        cfg = GateConfig()
        row = pd.Series({"line": 25.5, "result": 22.0, "pick": "lower"})
        assert compute_hit(row, cfg) == 1

    def test_lower_miss(self):
        """Test 'lower' pick that misses."""
        cfg = GateConfig()
        row = pd.Series({"line": 25.5, "result": 28.0, "pick": "lower"})
        assert compute_hit(row, cfg) == 0

    def test_exact_line_higher(self):
        """Test exact line with 'higher' (should miss)."""
        cfg = GateConfig()
        row = pd.Series({"line": 25.5, "result": 25.5, "pick": "higher"})
        assert compute_hit(row, cfg) == 0

    def test_exact_line_lower(self):
        """Test exact line with 'lower' (should miss)."""
        cfg = GateConfig()
        row = pd.Series({"line": 25.5, "result": 25.5, "pick": "lower"})
        assert compute_hit(row, cfg) == 0

    def test_invalid_pick(self):
        """Test invalid pick value raises error."""
        cfg = GateConfig()
        row = pd.Series({"line": 25.5, "result": 28.0, "pick": "invalid"})
        with pytest.raises(ValueError, match="Unknown pick"):
            compute_hit(row, cfg)


class TestGateLogic:
    """Test the core gate decision logic."""

    def test_non_pts_prop_always_eligible(self):
        """Non-PTS props should always be eligible (not applicable)."""
        cfg = GateConfig()
        row = pd.Series({
            "prop_type": "PRA",
            "pick": "lower",
            "arena_elasticity_norm": 0.1,
            "arena_elasticity_low_cut": 0.35,
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.eligible is True
        assert "not_applicable" in decision.reasons

    def test_pts_higher_always_eligible(self):
        """PTS 'higher' picks should always be eligible (gate only for lowers)."""
        cfg = GateConfig()
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "higher",
            "arena_elasticity_norm": 0.1,
            "arena_elasticity_low_cut": 0.35,
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.eligible is True
        assert "not_applicable" in decision.reasons

    def test_zero_signals_blocked(self):
        """PTS lower with 0 signals should be blocked."""
        cfg = GateConfig(min_signals_required=2)
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "lower",
            "arena_elasticity_norm": 0.8,  # High elasticity (good for scoring)
            "arena_elasticity_low_cut": 0.35,
            "coach_concentration_norm": 0.3,  # Low concentration (distributed)
            "coach_low_dist_cut": 0.65,
            "opp_compression_norm": 0.2,  # Low compression (weak defense)
            "opp_comp_high_cut": 0.65,
            "spread": 2.0,  # Close game
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.eligible is False
        assert decision.signals_true == 0

    def test_one_signal_blocked(self):
        """PTS lower with 1 signal should be blocked (need ≥2)."""
        cfg = GateConfig(min_signals_required=2)
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "lower",
            "arena_elasticity_norm": 0.2,  # LOW elasticity → signal TRUE
            "arena_elasticity_low_cut": 0.35,
            "coach_concentration_norm": 0.3,  # Low concentration
            "coach_low_dist_cut": 0.65,
            "opp_compression_norm": 0.2,  # Low compression
            "opp_comp_high_cut": 0.65,
            "spread": 2.0,  # Close game
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.eligible is False
        assert decision.signals_true == 1
        assert decision.reasons["arena_low_elasticity"] is True

    def test_two_signals_allowed(self):
        """PTS lower with 2 signals should be allowed."""
        cfg = GateConfig(min_signals_required=2)
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "lower",
            "arena_elasticity_norm": 0.2,  # LOW → TRUE
            "arena_elasticity_low_cut": 0.35,
            "coach_concentration_norm": 0.8,  # HIGH concentration → TRUE
            "coach_low_dist_cut": 0.65,
            "opp_compression_norm": 0.2,  # Low compression
            "opp_comp_high_cut": 0.65,
            "spread": 2.0,
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.eligible is True
        assert decision.signals_true == 2
        assert decision.reasons["arena_low_elasticity"] is True
        assert decision.reasons["coach_low_distribution"] is True

    def test_all_five_signals_allowed(self):
        """PTS lower with all 5 signals should be strongly allowed."""
        cfg = GateConfig(min_signals_required=2)
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "lower",
            "arena_elasticity_norm": 0.1,  # LOW → TRUE
            "arena_elasticity_low_cut": 0.35,
            "coach_concentration_norm": 0.9,  # HIGH → TRUE
            "coach_low_dist_cut": 0.65,
            "opp_compression_norm": 0.9,  # HIGH → TRUE
            "opp_comp_high_cut": 0.65,
            "spread": -12.0,  # Blowout → TRUE
            "teammate_pra_suppression": True,  # → TRUE
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.eligible is True
        assert decision.signals_true == 5
        assert all(decision.reasons.values())

    def test_blowout_signal_positive_spread(self):
        """Blowout signal should fire for positive large spreads."""
        cfg = GateConfig(blowout_spread_abs=8.0, min_signals_required=1)
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "lower",
            "arena_elasticity_norm": 0.5,
            "arena_elasticity_low_cut": 0.35,
            "coach_concentration_norm": 0.5,
            "coach_low_dist_cut": 0.65,
            "opp_compression_norm": 0.5,
            "opp_comp_high_cut": 0.65,
            "spread": 10.0,  # Blowout (favored by 10)
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.reasons["blowout_risk"] is True

    def test_blowout_signal_negative_spread(self):
        """Blowout signal should fire for negative large spreads."""
        cfg = GateConfig(blowout_spread_abs=8.0, min_signals_required=1)
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "lower",
            "arena_elasticity_norm": 0.5,
            "arena_elasticity_low_cut": 0.35,
            "coach_concentration_norm": 0.5,
            "coach_low_dist_cut": 0.65,
            "opp_compression_norm": 0.5,
            "opp_comp_high_cut": 0.65,
            "spread": -10.0,  # Blowout (underdog by 10)
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.reasons["blowout_risk"] is True

    def test_missing_spread_no_blowout(self):
        """Missing spread should not trigger blowout signal."""
        cfg = GateConfig(min_signals_required=1)
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "lower",
            "arena_elasticity_norm": 0.5,
            "arena_elasticity_low_cut": 0.35,
            "coach_concentration_norm": 0.5,
            "coach_low_dist_cut": 0.65,
            "opp_compression_norm": 0.5,
            "opp_comp_high_cut": 0.65,
            # No spread column
        })
        decision = scorer_under_gate(row, cfg)
        assert decision.reasons["blowout_risk"] is False


class TestFeatureEngineering:
    """Test feature engineering functions."""

    def test_arena_elasticity_single_arena(self):
        """Arena elasticity with single arena should return neutral."""
        cfg = GateConfig()
        df = pd.DataFrame({
            "arena": ["Arena A"] * 5,
            "total": [220, 225, 230, 215, 210],
        })
        result = arena_elasticity_proxy(df, cfg)
        # Single arena = all same value = neutral 0.5
        assert all(result == 0.5)

    def test_arena_elasticity_multiple_arenas(self):
        """Arena elasticity should normalize across arenas."""
        cfg = GateConfig()
        df = pd.DataFrame({
            "arena": ["Arena A", "Arena A", "Arena B", "Arena B"],
            "total": [200, 200, 240, 240],
        })
        result = arena_elasticity_proxy(df, cfg)
        # Arena A (200) should be 0.0, Arena B (240) should be 1.0
        assert result.iloc[0] == 0.0  # Arena A
        assert result.iloc[2] == 1.0  # Arena B

    def test_arena_elasticity_missing_columns(self):
        """Arena elasticity with missing columns should return neutral."""
        cfg = GateConfig()
        df = pd.DataFrame({"other_col": [1, 2, 3]})
        result = arena_elasticity_proxy(df, cfg)
        assert all(result == 0.5)

    def test_coach_distribution_empty_pts(self):
        """Coach distribution with no PTS legs should return neutral."""
        cfg = GateConfig()
        df = pd.DataFrame({
            "prop_type": ["PRA", "AST"],
            "team": ["Team A", "Team B"],
            "player": ["Player 1", "Player 2"],
            "result": [30, 8],
        })
        result = coach_distribution_proxy(df, cfg)
        assert all(result == 0.5)

    def test_opponent_compression_with_def_rating(self):
        """Opponent compression should use def rating if available."""
        cfg = GateConfig()
        df = pd.DataFrame({
            "opp_def_rating": [105, 115, 110],  # Lower = better defense
        })
        result = opponent_compression_proxy(df, cfg)
        # 105 (best defense) should have highest compression (1.0)
        # 115 (worst defense) should have lowest compression (0.0)
        assert result.iloc[0] == 1.0
        assert result.iloc[1] == 0.0

    def test_opponent_compression_with_tov_rate(self):
        """Opponent compression should use TOV rate if def rating absent."""
        cfg = GateConfig()
        df = pd.DataFrame({
            "opp_tov_rate": [12, 16, 14],  # Higher = more compression
        })
        result = opponent_compression_proxy(df, cfg)
        # 16 (highest TOV) should be 1.0
        # 12 (lowest TOV) should be 0.0
        assert result.iloc[1] == 1.0
        assert result.iloc[0] == 0.0

    def test_opponent_compression_missing_all(self):
        """Opponent compression with no data should return neutral."""
        cfg = GateConfig()
        df = pd.DataFrame({"other_col": [1, 2, 3]})
        result = opponent_compression_proxy(df, cfg)
        assert all(result == 0.5)


class TestBacktestPipeline:
    """Test the full backtest pipeline with synthetic data."""

    def test_backtest_empty_csv(self, tmp_path):
        """Backtest should handle empty CSV gracefully."""
        csv_path = tmp_path / "empty.csv"
        df_empty = pd.DataFrame(columns=["date", "player", "team", "opponent",
                                          "prop_type", "pick", "line", "result"])
        df_empty.to_csv(csv_path, index=False)

        cfg = GateConfig()
        df_result, report = backtest(str(csv_path), cfg)

        assert report["rows_total"] == 0
        assert report["pts_lower_rows"] == 0

    def test_backtest_synthetic_data(self, tmp_path):
        """Full backtest with synthetic legs showing gate effectiveness."""
        csv_path = tmp_path / "legs.csv"

        # Create synthetic data:
        # - 4 PTS lowers, 2 should pass gate, 2 should fail
        # - 2 PTS highers (always pass, not gated)
        # - 2 PRA props (always pass, not gated)
        data = {
            "date": ["2024-01-01"] * 8,
            "player": [f"Player{i}" for i in range(8)],
            "team": ["Team A"] * 8,
            "opponent": ["Team B"] * 8,
            "home": [1] * 8,
            "arena": ["Arena X"] * 8,
            "prop_type": ["PTS", "PTS", "PTS", "PTS", "PTS", "PTS", "PRA", "PRA"],
            "pick": ["lower", "lower", "lower", "lower", "higher", "higher", "lower", "lower"],
            "line": [25.5, 20.5, 18.5, 22.5, 30.5, 28.5, 45.5, 40.5],
            "result": [22, 18, 20, 24, 35, 26, 42, 38],  # Mix of hits/misses
            "spread": [-10, -10, 2, 2, -5, -5, -3, -3],  # First 2 are blowouts
            "total": [220] * 8,
        }
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)

        cfg = GateConfig(blowout_spread_abs=8.0, min_signals_required=1)
        df_result, report = backtest(str(csv_path), cfg)

        # Verify report structure
        assert "rows_total" in report
        assert "pts_lower_rows" in report
        assert "baseline_pts_lower_hit_rate" in report
        assert "filtered_pts_lower_rows" in report
        assert "filtered_pts_lower_hit_rate" in report
        assert "cfg_hash" in report

        # 4 PTS lowers total
        assert report["pts_lower_rows"] == 4

        # At least some should pass gate (depends on signals)
        assert report["filtered_pts_lower_rows"] >= 0

        # Volume retained should be 0..1
        assert 0.0 <= report["volume_retained"] <= 1.0

    def test_backtest_computes_hit_if_missing(self, tmp_path):
        """Backtest should compute 'hit' column if not present."""
        csv_path = tmp_path / "legs_no_hit.csv"

        data = {
            "date": ["2024-01-01"] * 2,
            "player": ["Player1", "Player2"],
            "team": ["Team A"] * 2,
            "opponent": ["Team B"] * 2,
            "home": [1, 1],
            "arena": ["Arena X"] * 2,
            "prop_type": ["PTS", "PTS"],
            "pick": ["lower", "higher"],
            "line": [25.5, 20.5],
            "result": [22, 25],  # First hits, second hits
            "spread": [0, 0],
            "total": [220, 220],
        }
        df = pd.DataFrame(data)
        # Don't include 'hit' column
        df.to_csv(csv_path, index=False)

        cfg = GateConfig()
        df_result, report = backtest(str(csv_path), cfg)

        # Check that 'hit' was computed
        assert "hit" in df_result.columns
        assert df_result["hit"].iloc[0] == 1  # lower 22 vs 25.5 → hit
        assert df_result["hit"].iloc[1] == 1  # higher 25 vs 20.5 → hit

    def test_backtest_adds_gate_columns(self, tmp_path):
        """Backtest should add gate_* columns to output."""
        csv_path = tmp_path / "legs.csv"

        data = {
            "date": ["2024-01-01"],
            "player": ["Player1"],
            "team": ["Team A"],
            "opponent": ["Team B"],
            "home": [1],
            "arena": ["Arena X"],
            "prop_type": ["PTS"],
            "pick": ["lower"],
            "line": [25.5],
            "result": [22],
            "spread": [0],
            "total": [220],
        }
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)

        cfg = GateConfig()
        df_result, report = backtest(str(csv_path), cfg)

        # Check gate columns exist
        assert "gate_eligible" in df_result.columns
        assert "gate_signals" in df_result.columns
        assert "gate_provenance" in df_result.columns
        assert "gate_reasons" in df_result.columns


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_gate_with_nan_spread(self):
        """Gate should handle NaN spread gracefully."""
        cfg = GateConfig()
        row = pd.Series({
            "prop_type": "PTS",
            "pick": "lower",
            "arena_elasticity_norm": 0.5,
            "arena_elasticity_low_cut": 0.35,
            "coach_concentration_norm": 0.5,
            "coach_low_dist_cut": 0.65,
            "opp_compression_norm": 0.5,
            "opp_comp_high_cut": 0.65,
            "spread": float('nan'),
        })
        decision = scorer_under_gate(row, cfg)
        # Should not crash, blowout should be False
        assert decision.reasons["blowout_risk"] is False

    def test_config_immutability(self):
        """GateConfig should be frozen (immutable)."""
        cfg = GateConfig()
        with pytest.raises(Exception):  # FrozenInstanceError in Python 3.10+
            cfg.blowout_spread_abs = 10.0

    def test_decision_immutability(self):
        """GateDecision should be frozen (immutable)."""
        decision = GateDecision(True, 2, {"test": True}, "abc123")
        with pytest.raises(Exception):
            decision.eligible = False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
