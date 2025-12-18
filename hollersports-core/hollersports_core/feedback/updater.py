from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..schema.state import ModelState
from ..schema.expected import ExpectedOutcome
from ..schema.feedback import FeedbackMetrics


@dataclass(frozen=True)
class UpdatedPriors:
    fatigue_weight: float
    tempo_bias: float
    streak_compression: float


def _clip(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def update_state_with_feedback(
    state: ModelState,
    exp: ExpectedOutcome,
    m: FeedbackMetrics,
) -> tuple[ModelState, UpdatedPriors]:
    """
    Deterministic update:
    - tempo_bias nudged by sign of total residual (systematically under/over predicting totals)
    - fatigue_weight increased when surprise is high (model missing fatigue/variance), decreased when very low surprise
    - streak_compression nudged by abs spread residual (overconfident in edges => increase compression)
    Also maintains EMA of residual and residual variance for monitoring drift.
    """
    beta = state.ema_beta

    # Update EMAs (classic online)
    new_mean = (1 - beta) * state.total_residual_ema + beta * m.residual_total
    # variance EMA around new_mean (stable)
    centered = m.residual_total - new_mean
    new_var = (1 - beta) * state.total_residual_var_ema + beta * float(centered * centered)
    new_var = max(new_var, 1e-6)

    # Signals
    sign_total = float(np.sign(m.residual_total))  # -1,0,1
    # Use surprise in [0,3)
    surprise = m.surprise

    # Tempo: if we keep underpredicting totals (residual_total positive), increase tempo_bias.
    new_tempo = state.tempo_bias + state.lr_tempo * sign_total * min(1.0, surprise / 2.0)

    # Fatigue: if surprise high, increase fatigue_weight slightly; if very low surprise, ease off.
    fatigue_delta = (surprise - 1.0)  # >0 means "more surprise than baseline"
    new_fatigue = state.fatigue_weight + state.lr_fatigue * fatigue_delta

    # Streak compression: if spread residual is large, compress edges (be more conservative)
    abs_spread_resid = abs(m.residual_spread_home)
    # normalize by a crude scale to keep stable across sports; uses sigma_total as proxy
    scale = max(exp.sigma_total, 1.0)
    compression_delta = min(1.0, abs_spread_resid / (2.0 * scale))
    new_streak = state.streak_compression + state.lr_streak * compression_delta

    # Clip to safe ranges
    new_tempo = _clip(new_tempo, -10.0, 10.0)
    new_fatigue = _clip(new_fatigue, 0.0, 5.0)
    new_streak = _clip(new_streak, 0.1, 3.0)

    updated = state.model_copy(update={
        "tempo_bias": new_tempo,
        "fatigue_weight": new_fatigue,
        "streak_compression": new_streak,
        "total_residual_ema": float(new_mean),
        "total_residual_var_ema": float(new_var),
    })

    return updated, UpdatedPriors(
        fatigue_weight=new_fatigue,
        tempo_bias=new_tempo,
        streak_compression=new_streak,
    )
