"""Continuous Ranked Probability Score helpers (distributional eval)."""

from __future__ import annotations

from typing import Sequence


def crps_ensemble(samples: Sequence[float], observation: float) -> float:
    """CRPS for an empirical ensemble (Gneiting & Raftery form)."""
    if not samples:
        return 0.0
    n = len(samples)
    obs = float(observation)
    term1 = sum(abs(float(s) - obs) for s in samples) / n
    term2 = 0.0
    for i, a in enumerate(samples):
        for b in samples[i + 1 :]:
            term2 += abs(float(a) - float(b))
    term2 = term2 / (n * n) if n else 0.0
    # standard empirical: mean|x-y| - 0.5 mean|x-x'|
    return term1 - 0.5 * (2.0 * term2)


def crps_categorical(probs: Sequence[float], outcome_bin: int) -> float:
    """CRPS for discrete distribution over bins 0..K-1 (cumulative form).

    ``probs`` must sum ~1; ``outcome_bin`` in range.
    """
    if not probs:
        return 0.0
    k = len(probs)
    y = max(0, min(k - 1, int(outcome_bin)))
    # cumulative forecast CDF
    cdf = []
    s = 0.0
    for p in probs:
        s += max(0.0, float(p))
        cdf.append(s)
    # normalize if needed
    if s > 0 and abs(s - 1.0) > 1e-6:
        cdf = [c / s for c in cdf]
    total = 0.0
    for i in range(k):
        f = cdf[i]
        o = 1.0 if i >= y else 0.0
        total += (f - o) ** 2
    return total


def expected_bin(probs: Sequence[float]) -> float:
    if not probs:
        return 0.0
    s = sum(max(0.0, float(p)) for p in probs) or 1.0
    return sum(i * max(0.0, float(p)) / s for i, p in enumerate(probs))
