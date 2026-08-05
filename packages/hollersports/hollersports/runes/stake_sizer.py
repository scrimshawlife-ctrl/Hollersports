"""Deterministic paper stake sizing (no live capital)."""

from __future__ import annotations


def size_stake(
    *,
    bankroll: float,
    score: float,
    human_max_stake: float,
) -> float:
    """Compute paper stake: min(human_max_stake, bankroll * 0.01 * score).

    Deterministic; non-negative. Callers must reject or re-check if stake is 0
    when approval is required.
    """
    bankroll_f = max(0.0, float(bankroll))
    score_f = max(0.0, min(1.0, float(score)))
    max_stake = max(0.0, float(human_max_stake))
    raw = bankroll_f * 0.01 * score_f
    return min(max_stake, raw)
