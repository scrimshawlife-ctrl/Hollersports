"""
Tests for NFL Monte Carlo simulation.

Validates 150k-run simulation with market-specific distributions.
"""

import pytest
from hollersports.nfl.types import Side, Market
from hollersports.nfl.monte_carlo import run_monte_carlo, estimate_confidence_from_distribution


class TestMonteCarlo:
    """Test Monte Carlo simulation."""

    def test_deterministic_with_same_seed(self):
        """Same seed should produce identical results."""
        config = {"n_sims": 150000, "seed": 1337}

        result1 = run_monte_carlo(
            mu=6.0,
            sigma=2.0,
            line=5.5,
            side=Side.HIGHER,
            market=Market.RECEPTIONS,
            config=config,
        )

        result2 = run_monte_carlo(
            mu=6.0,
            sigma=2.0,
            line=5.5,
            side=Side.HIGHER,
            market=Market.RECEPTIONS,
            config=config,
        )

        assert result1.p_hit == result2.p_hit
        assert result1.mean == result2.mean
        assert result1.p50 == result2.p50

    def test_higher_line_reasonable_p_hit(self):
        """Over bet with mu > line should have p_hit > 0.5."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(
            mu=7.0,
            sigma=2.0,
            line=5.5,
            side=Side.HIGHER,
            market=Market.RECEPTIONS,
            config=config,
        )

        assert result.p_hit > 0.5
        assert result.p_hit < 1.0

    def test_lower_line_reasonable_p_hit(self):
        """Under bet with mu < line should have p_hit > 0.5."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(
            mu=4.0,
            sigma=1.5,
            line=5.5,
            side=Side.LOWER,
            market=Market.RECEPTIONS,
            config=config,
        )

        assert result.p_hit > 0.5
        assert result.p_hit < 1.0

    def test_distribution_statistics(self):
        """Should produce valid distribution statistics."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(
            mu=6.0,
            sigma=2.0,
            line=5.5,
            side=Side.HIGHER,
            market=Market.RECEPTIONS,
            config=config,
        )

        # Mean should be close to mu
        assert abs(result.mean - 6.0) < 1.0

        # Percentiles should be ordered
        assert result.p10 < result.p25 < result.p50 < result.p75 < result.p90

        # Median should be close to mean for count data
        assert abs(result.p50 - result.mean) < 1.5

    def test_runs_150k_simulations(self):
        """Should run exactly 150,000 simulations."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(
            mu=6.0,
            sigma=2.0,
            line=5.5,
            side=Side.HIGHER,
            market=Market.RECEPTIONS,
            config=config,
        )

        assert result.n_sims == 150000

    def test_negative_binomial_for_count_data(self):
        """Count markets should use Negative Binomial."""
        config = {"n_sims": 150000, "seed": 1337}

        # High variance count data
        result = run_monte_carlo(
            mu=5.0,
            sigma=3.0,
            line=4.5,
            side=Side.HIGHER,
            market=Market.TARGETS,
            config=config,
        )

        assert 0.0 < result.p_hit < 1.0
        assert result.mean > 0

    def test_gamma_for_yardage_data(self):
        """Yardage markets should use Gamma distribution."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(
            mu=65.0,
            sigma=25.0,
            line=60.5,
            side=Side.HIGHER,
            market=Market.REC_YDS,
            config=config,
        )

        assert 0.0 < result.p_hit < 1.0
        assert result.mean > 0

    def test_poisson_for_touchdowns(self):
        """Touchdown markets should use Poisson."""
        config = {"n_sims": 150000, "seed": 1337}

        result = run_monte_carlo(
            mu=0.6,
            sigma=0.8,
            line=0.5,
            side=Side.HIGHER,
            market=Market.REC_TD,
            config=config,
        )

        assert 0.0 < result.p_hit < 1.0


class TestEstimateConfidence:
    """Test confidence estimation."""

    def test_high_p_hit_boosts_confidence(self):
        """High p_hit should result in high confidence."""
        from hollersports.nfl.types import MonteCarloResult

        mc_result = MonteCarloResult(
            p_hit=0.75,
            mean=7.0,
            std=2.0,
            p10=4.0,
            p25=5.0,
            p50=7.0,
            p75=9.0,
            p90=10.0,
        )

        confidence = estimate_confidence_from_distribution(
            mc_result, median=7.0, floor=5.5, line=5.5, side=Side.HIGHER
        )

        assert confidence >= 0.70

    def test_safe_floor_boosts_confidence(self):
        """Floor above line (for over) should boost confidence."""
        from hollersports.nfl.types import MonteCarloResult

        mc_result = MonteCarloResult(
            p_hit=0.65,
            mean=7.0,
            std=2.0,
            p10=4.0,
            p25=5.5,
            p50=7.0,
            p75=9.0,
            p90=10.0,
        )

        confidence = estimate_confidence_from_distribution(
            mc_result, median=7.0, floor=6.0, line=5.5, side=Side.HIGHER
        )

        assert confidence > mc_result.p_hit  # Should get boost

    def test_confidence_bounded(self):
        """Confidence should be bounded to [0, 1]."""
        from hollersports.nfl.types import MonteCarloResult

        mc_result = MonteCarloResult(
            p_hit=0.95,
            mean=12.0,
            std=1.0,
            p10=10.0,
            p25=11.0,
            p50=12.0,
            p75=13.0,
            p90=14.0,
        )

        confidence = estimate_confidence_from_distribution(
            mc_result, median=12.0, floor=11.0, line=8.5, side=Side.HIGHER
        )

        assert 0.0 <= confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
