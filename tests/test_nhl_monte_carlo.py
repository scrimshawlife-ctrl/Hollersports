"""
Tests for NHL Monte Carlo simulation.

Validates 150k-run simulation with deterministic results.
"""

import pytest

from hollersports.nhl.types import Side
from hollersports.nhl.monte_carlo import run_monte_carlo, estimate_confidence_from_distribution


class TestMonteCarlo:
    """Test Monte Carlo simulation."""

    def test_deterministic_with_same_seed(self):
        """Same seed should produce identical results."""
        config = {"n_sims": 150000, "seed": 1337}

        result1 = run_monte_carlo(mu=4.0, sigma=1.5, line=3.5, side=Side.HIGHER, config=config)
        result2 = run_monte_carlo(mu=4.0, sigma=1.5, line=3.5, side=Side.HIGHER, config=config)

        assert result1.p_hit == result2.p_hit
        assert result1.mean == result2.mean
        assert result1.p50 == result2.p50

    def test_higher_line_reasonable_p_hit(self):
        """Over bet with mu > line should have p_hit > 0.5."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(mu=5.0, sigma=1.5, line=4.0, side=Side.HIGHER, config=config)

        assert result.p_hit > 0.5
        assert result.p_hit < 1.0

    def test_lower_line_reasonable_p_hit(self):
        """Under bet with mu < line should have p_hit > 0.5."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(mu=3.0, sigma=1.5, line=4.0, side=Side.LOWER, config=config)

        assert result.p_hit > 0.5
        assert result.p_hit < 1.0

    def test_distribution_statistics(self):
        """Should produce valid distribution statistics."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(mu=4.0, sigma=1.5, line=3.5, side=Side.HIGHER, config=config)

        # Mean should be close to mu
        assert abs(result.mean - 4.0) < 0.5

        # Percentiles should be ordered
        assert result.p10 < result.p25 < result.p50 < result.p75 < result.p90

        # Median should be close to mean for count data
        assert abs(result.p50 - result.mean) < 1.0

    def test_runs_150k_simulations(self):
        """Should run exactly 150,000 simulations."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(mu=4.0, sigma=1.5, line=3.5, side=Side.HIGHER, config=config)

        assert result.n_sims == 150000

    def test_negative_binomial_vs_poisson(self):
        """Negative Binomial should handle overdispersion."""
        config_nb = {"n_sims": 150000, "seed": 1337, "use_negative_binomial": True}
        config_poisson = {"n_sims": 150000, "seed": 1337, "use_negative_binomial": False}

        # High variance case
        result_nb = run_monte_carlo(mu=4.0, sigma=3.0, line=3.5, side=Side.HIGHER, config=config_nb)
        result_poisson = run_monte_carlo(mu=4.0, sigma=3.0, line=3.5, side=Side.HIGHER, config=config_poisson)

        # Both should be valid, but NB should handle overdispersion better
        assert 0.0 < result_nb.p_hit < 1.0
        assert 0.0 < result_poisson.p_hit < 1.0


class TestEstimateConfidence:
    """Test confidence estimation."""

    def test_high_p_hit_boosts_confidence(self):
        """High p_hit should result in high confidence."""
        from hollersports.nhl.types import MonteCarloResult

        mc_result = MonteCarloResult(
            p_hit=0.75,
            mean=5.0,
            std=1.5,
            p10=3.0,
            p25=4.0,
            p50=5.0,
            p75=6.0,
            p90=7.0,
        )

        confidence = estimate_confidence_from_distribution(
            mc_result, median=5.0, floor=4.5, line=4.0, side=Side.HIGHER
        )

        assert confidence >= 0.70

    def test_safe_floor_boosts_confidence(self):
        """Floor above line (for over) should boost confidence."""
        from hollersports.nhl.types import MonteCarloResult

        mc_result = MonteCarloResult(
            p_hit=0.65,
            mean=5.0,
            std=1.5,
            p10=3.0,
            p25=4.0,
            p50=5.0,
            p75=6.0,
            p90=7.0,
        )

        confidence = estimate_confidence_from_distribution(
            mc_result, median=5.0, floor=4.5, line=4.0, side=Side.HIGHER
        )

        assert confidence > mc_result.p_hit  # Should get boost

    def test_confidence_bounded(self):
        """Confidence should be bounded to [0, 1]."""
        from hollersports.nhl.types import MonteCarloResult

        mc_result = MonteCarloResult(
            p_hit=0.95,
            mean=10.0,
            std=0.5,
            p10=9.0,
            p25=9.5,
            p50=10.0,
            p75=10.5,
            p90=11.0,
        )

        confidence = estimate_confidence_from_distribution(
            mc_result, median=10.0, floor=9.5, line=5.0, side=Side.HIGHER
        )

        assert 0.0 <= confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
