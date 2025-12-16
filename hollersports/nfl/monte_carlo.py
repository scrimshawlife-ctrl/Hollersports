"""
Monte Carlo simulation for NFL props.

150,000-run standard with market-specific distributions.
"""

import numpy as np
from hollersports.nfl.types import Side, Market, MonteCarloResult


def run_monte_carlo(
    mu: float,
    sigma: float,
    line: float,
    side: Side,
    market: Market,
    config: dict,
) -> MonteCarloResult:
    """
    Run 150k Monte Carlo simulation.

    Args:
        mu: Mean projection
        sigma: Standard deviation
        line: Prop line
        side: HIGHER or LOWER
        market: Market type (determines distribution)
        config: Configuration dict

    Returns:
        MonteCarloResult with p_hit and percentiles
    """
    n_sims = config.get("n_sims", 150000)
    seed = config.get("seed", 1337)

    np.random.seed(seed)

    # Choose distribution based on market type
    if market in (Market.RECEPTIONS, Market.TARGETS, Market.RUSH_ATT):
        # Count data: Negative Binomial (overdispersed Poisson)
        samples = _sample_negative_binomial(mu, sigma, n_sims)
    elif market in (Market.REC_YDS, Market.RUSH_YDS, Market.PASS_YDS):
        # Yardage: Gamma distribution (right-skewed, non-negative)
        samples = _sample_gamma(mu, sigma, n_sims)
    elif market in (Market.PASS_ATT,):
        # Pass attempts: Negative Binomial
        samples = _sample_negative_binomial(mu, sigma, n_sims)
    elif market in (Market.REC_TD, Market.RUSH_TD, Market.PASS_TD):
        # Touchdowns: Poisson (low mean, discrete)
        samples = _sample_poisson(mu, n_sims)
    else:
        # Default: Normal (fallback)
        samples = np.random.normal(mu, sigma, size=n_sims)
        samples = np.maximum(samples, 0)  # Non-negative

    # Compute hit probability
    if side == Side.HIGHER:
        hits = np.sum(samples > line)
    else:  # Side.LOWER
        hits = np.sum(samples < line)

    p_hit = hits / n_sims

    # Compute statistics
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


def _sample_negative_binomial(mu: float, sigma: float, n: int) -> np.ndarray:
    """
    Sample from Negative Binomial distribution.

    Handles overdispersion (variance > mean).
    """
    if mu <= 0:
        return np.zeros(n)

    var = sigma ** 2

    # If variance <= mean, use Poisson
    if var <= mu:
        return np.random.poisson(mu, size=n)

    # Negative Binomial parameterization
    # var = mu + mu^2 / r
    # r = mu^2 / (var - mu)
    r = (mu ** 2) / (var - mu)
    r = max(r, 0.1)  # Avoid numerical issues

    # p = r / (r + mu)
    p = r / (r + mu)
    p = min(max(p, 0.001), 0.999)  # Clamp to valid range

    samples = np.random.negative_binomial(r, p, size=n)
    return samples.astype(float)


def _sample_gamma(mu: float, sigma: float, n: int) -> np.ndarray:
    """
    Sample from Gamma distribution.

    Suitable for right-skewed continuous data (yardage).
    """
    if mu <= 0:
        return np.zeros(n)

    var = sigma ** 2

    # Gamma parameterization: shape (k), scale (theta)
    # mean = k * theta
    # var = k * theta^2
    # => k = mean^2 / var, theta = var / mean

    k = (mu ** 2) / var if var > 0 else 1.0
    k = max(k, 0.1)  # Avoid numerical issues

    theta = var / mu if mu > 0 and var > 0 else mu
    theta = max(theta, 0.1)

    samples = np.random.gamma(k, theta, size=n)
    return samples


def _sample_poisson(mu: float, n: int) -> np.ndarray:
    """
    Sample from Poisson distribution.

    For low-mean count data (touchdowns).
    """
    if mu <= 0:
        return np.zeros(n)

    samples = np.random.poisson(mu, size=n)
    return samples.astype(float)


def estimate_confidence_from_distribution(
    mc_result: MonteCarloResult,
    median: float,
    floor: float,
    line: float,
    side: Side,
) -> float:
    """
    Estimate confidence score from Monte Carlo results.

    Args:
        mc_result: Monte Carlo simulation result
        median: Median projection
        floor: Floor projection
        line: Prop line
        side: HIGHER or LOWER

    Returns:
        Confidence score [0, 1]

    Model:
        - Base confidence = p_hit
        - Boost if floor is safe relative to line
        - Boost if p25/p75 are on correct side of line
        - Cap at 0.95
    """
    confidence = mc_result.p_hit

    # Floor safety boost
    if side == Side.HIGHER:
        # For overs: floor > line is very confident
        if floor > line:
            floor_boost = min(0.10, (floor - line) / line * 0.05)
            confidence += floor_boost
        # Check p25
        if mc_result.p25 > line:
            confidence += 0.05
    else:  # Side.LOWER
        # For unders: floor < line is confident
        if floor < line:
            floor_boost = min(0.10, (line - floor) / line * 0.05)
            confidence += floor_boost
        # Check p75
        if mc_result.p75 < line:
            confidence += 0.05

    # IQR tightness boost (narrow distribution = more confident)
    iqr = mc_result.p75 - mc_result.p25
    if median > 0:
        iqr_ratio = iqr / median
        if iqr_ratio < 0.5:  # Tight distribution
            confidence += 0.03

    # Cap at 0.95
    confidence = min(confidence, 0.95)

    # Floor at 0.0
    confidence = max(confidence, 0.0)

    return confidence
