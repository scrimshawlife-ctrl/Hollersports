"""
Tests for NFL script state probability tree.

Validates vegas spread → script probabilities.
"""

import pytest
from hollersports.nfl.types import ScriptState, Market
from hollersports.nfl.script_tree import (
    compute_script_priors,
    get_script_modifier,
    compute_script_weighted_median,
)


class TestComputeScriptPriors:
    """Test script prior computation."""

    def test_no_vegas_context_balanced(self):
        """No vegas data should produce balanced priors."""
        priors = compute_script_priors(vegas_spread=None)

        assert priors[ScriptState.NEUTRAL] == 0.70
        assert priors[ScriptState.LEADING] == 0.10
        assert priors[ScriptState.TRAILING] == 0.10
        assert priors[ScriptState.TWO_MINUTE] == 0.10

        # Should sum to 1.0
        assert abs(sum(priors.values()) - 1.0) < 0.001

    def test_favored_team_more_leading(self):
        """Favored team (negative spread) should have more leading time."""
        priors = compute_script_priors(vegas_spread=-7.0)

        # Should have more leading share
        assert priors[ScriptState.LEADING] > priors[ScriptState.TRAILING]

        # Should sum to 1.0
        assert abs(sum(priors.values()) - 1.0) < 0.001

    def test_underdog_team_more_trailing(self):
        """Underdog team (positive spread) should have more trailing time."""
        priors = compute_script_priors(vegas_spread=7.0)

        # Should have more trailing share
        assert priors[ScriptState.TRAILING] > priors[ScriptState.LEADING]

        # Should sum to 1.0
        assert abs(sum(priors.values()) - 1.0) < 0.001

    def test_large_spread_reduces_neutral(self):
        """Large spread should reduce neutral share."""
        priors_small = compute_script_priors(vegas_spread=-3.0)
        priors_large = compute_script_priors(vegas_spread=-10.0)

        # Larger spread = less neutral time
        assert priors_large[ScriptState.NEUTRAL] < priors_small[ScriptState.NEUTRAL]

    def test_priors_sum_to_one(self):
        """All priors should sum to 1.0."""
        for spread in [-14.0, -7.0, -3.0, 0.0, 3.0, 7.0, 14.0]:
            priors = compute_script_priors(vegas_spread=spread)
            assert abs(sum(priors.values()) - 1.0) < 0.001


class TestGetScriptModifier:
    """Test script state modifiers."""

    def test_neutral_no_modifier(self):
        """Neutral script should have no modifier."""
        mod = get_script_modifier(ScriptState.NEUTRAL, "RECEPTIONS", "WR")
        assert mod == 1.0

    def test_leading_rb_rush_boost(self):
        """Leading script should boost RB rushing."""
        mod = get_script_modifier(ScriptState.LEADING, "RUSH_ATT", "RB")
        assert mod > 1.0

    def test_leading_wr_targets_penalty(self):
        """Leading script should reduce WR targets."""
        mod = get_script_modifier(ScriptState.LEADING, "TARGETS", "WR")
        assert mod < 1.0

    def test_trailing_rb_rush_penalty(self):
        """Trailing script should reduce RB rushing."""
        mod = get_script_modifier(ScriptState.TRAILING, "RUSH_ATT", "RB")
        assert mod < 1.0

    def test_trailing_wr_targets_boost(self):
        """Trailing script should boost WR targets."""
        mod = get_script_modifier(ScriptState.TRAILING, "TARGETS", "WR")
        assert mod > 1.0

    def test_two_minute_rb_receptions_boost(self):
        """Two-minute script should boost RB receptions (checkdowns)."""
        mod = get_script_modifier(ScriptState.TWO_MINUTE, "RECEPTIONS", "RB")
        assert mod > 1.0


class TestComputeScriptWeightedMedian:
    """Test script-weighted median calculation."""

    def test_neutral_script_no_change(self):
        """100% neutral script should not change median."""
        priors = {
            ScriptState.NEUTRAL: 1.0,
            ScriptState.LEADING: 0.0,
            ScriptState.TRAILING: 0.0,
            ScriptState.TWO_MINUTE: 0.0,
        }

        median = compute_script_weighted_median(
            neutral_median=5.0,
            script_priors=priors,
            market="RECEPTIONS",
            position="WR",
        )

        assert abs(median - 5.0) < 0.01

    def test_leading_script_reduces_wr_targets(self):
        """Leading script should reduce WR targets median."""
        priors = {
            ScriptState.NEUTRAL: 0.0,
            ScriptState.LEADING: 1.0,
            ScriptState.TRAILING: 0.0,
            ScriptState.TWO_MINUTE: 0.0,
        }

        median = compute_script_weighted_median(
            neutral_median=6.0,
            script_priors=priors,
            market="TARGETS",
            position="WR",
        )

        assert median < 6.0  # Should be reduced

    def test_trailing_script_boosts_wr_targets(self):
        """Trailing script should boost WR targets median."""
        priors = {
            ScriptState.NEUTRAL: 0.0,
            ScriptState.LEADING: 0.0,
            ScriptState.TRAILING: 1.0,
            ScriptState.TWO_MINUTE: 0.0,
        }

        median = compute_script_weighted_median(
            neutral_median=6.0,
            script_priors=priors,
            market="TARGETS",
            position="WR",
        )

        assert median > 6.0  # Should be boosted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
