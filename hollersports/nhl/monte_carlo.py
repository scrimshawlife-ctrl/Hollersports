"""
Monte Carlo Simulation for NHL SOG projections.

150,000-run standard using Negative Binomial distribution for count data.
"""

import numpy as np
from hollersports.nhl.types import MonteCarloResult, Side


# Default configuration
DEFAULT_CONFIG = {
    "n_sims": 150000,
    "seed": 1337,
    "use_negative_binomial": True,  # More realistic for count data
}


def run_monte_carlo(
    mu: float,
    sigma: float,
    line: float,
    side: Side,
    config: dict = None,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation for SOG projection.

    Uses Negative Binomial distribution (overdispersed Poisson) for realism.

    Args:
        mu: Mean projection
        sigma: Standard deviation estimate
        line: Prop line to evaluate
        side: HIGHER or LOWER
        config: Optional configuration

    Returns:
        MonteCarloResult with p_hit and distribution statistics
    """
    if config is None:
        config = DEFAULT_CONFIG

    n_sims = config.get("n_sims", 150000)
    seed = config.get("seed", 1337)
    use_nb = config.get("use_negative_binomial", True)

    # Set random seed for reproducibility
    np.random.seed(seed)

    # Generate samples
    if use_nb and sigma > 0:
        # Negative Binomial: overdispersed Poisson
        # Parameterize using mean and variance
        # var = mu + mu^2 / r
        # Solve for r: r = mu^2 / (var - mu)

        var = sigma ** 2

        if var > mu:
            r = (mu ** 2) / (var - mu)
            p = r / (r + mu)

            # Ensure valid parameters
            r = max(0.1, min(1000, r))
            p = max(0.001, min(0.999, p))

            samples = np.random.negative_binomial(r, p, size=n_sims)
        else:
            # Fallback to Poisson if variance too low
            samples = np.random.poisson(mu, size=n_sims)

    else:
        # Simple Poisson
        samples = np.random.poisson(max(0.1, mu), size=n_sims)

    # Compute p_hit
    if side == Side.HIGHER:
        hits = np.sum(samples > line)
    else:  # LOWER
        hits = np.sum(samples < line)

    p_hit = hits / n_sims

    # Compute distribution statistics
    mean = float(np.mean(samples))
    std = float(np.std(samples))
    p10 = float(np.percentile(samples, 10))
    p25 = float(np.percentile(samples, 25))
    p50 = float(np.percentile(samples, 50))
    p75 = float(np.percentile(samples, 75))
    p90 = float(np.percentile(samples, 90))

    return MonteCarloResult(
        p_hit=p_hit,
        mean=mean,
        std=std,
        p10=p10,
        p25=p25,
        p50=p50,
        p75=p75,
        p90=p90,
        n_sims=n_sims,
    )


def estimate_confidence_from_distribution(
    mc_result: MonteCarloResult,
    median: float,
    floor: float,
    line: float,
    side: Side,
) -> float:
    """
    Estimate overall confidence from Monte Carlo + median-floor analysis.

    Args:
        mc_result: Monte Carlo simulation result
        median: Median projection
        floor: Conservative floor
        line: Prop line
        side: HIGHER or LOWER

    Returns:
        Confidence score (0-1)
    """
    # Base confidence from p_hit
    confidence = mc_result.p_hit

    # Adjust based on floor relative to line
    if side == Side.HIGHER:
        # Over: want floor close to or above line
        if floor >= line:
            confidence = min(1.0, confidence + 0.05)  # Boost
        elif floor < line * 0.9:
            confidence = max(0.0, confidence - 0.05)  # Penalize

    else:  # LOWER
        # Under: want floor well below line
        if floor < line * 0.8:
            confidence = min(1.0, confidence + 0.05)  # Boost
        elif floor >= line:
            confidence = max(0.0, confidence - 0.05)  # Penalize

    # Adjust based on distribution spread
    # Tighter distribution = higher confidence
    if mc_result.std < 2.0:
        confidence = min(1.0, confidence + 0.03)
    elif mc_result.std > 4.0:
        confidence = max(0.0, confidence - 0.03)

    return confidence
