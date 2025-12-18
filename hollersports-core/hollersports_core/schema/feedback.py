from __future__ import annotations
from pydantic import BaseModel, Field
from .expected import ExpectedOutcome
from .result import GameResult


class FeedbackMetrics(BaseModel):
    game_id: str

    # Residuals
    residual_total: float
    residual_spread_home: float

    # Normalized residuals (z-like)
    z_total: float = Field(..., description="residual_total / sigma_total")

    # Variance delta signals
    abs_z_total: float
    surprise: float = Field(..., description="abs_z_total capped and smoothed")


class FeedbackRecord(BaseModel):
    expected: ExpectedOutcome
    result: GameResult
    metrics: FeedbackMetrics

    # Updated priors
    new_fatigue_weight: float
    new_tempo_bias: float
    new_streak_compression: float
