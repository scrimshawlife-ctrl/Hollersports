from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class ModelState(BaseModel):
    sport: Literal["NBA","NHL","NFL","MLB","WNBA","EPL","OTHER"] = "NBA"
    model_version: str = "hs-0.1.0"

    # Priors (these get updated by feedback)
    fatigue_weight: float = Field(default=1.0, ge=0.0, le=5.0)
    tempo_bias: float = Field(default=0.0, ge=-10.0, le=10.0)
    streak_compression: float = Field(default=1.0, ge=0.1, le=3.0)

    # Learning rates (kept small; deterministic)
    lr_fatigue: float = Field(default=0.02, ge=0.0, le=0.25)
    lr_tempo: float = Field(default=0.02, ge=0.0, le=0.25)
    lr_streak: float = Field(default=0.02, ge=0.0, le=0.25)

    # Stability/decay
    ema_beta: float = Field(default=0.10, ge=0.0, le=1.0)  # for variance EMA
    total_residual_ema: float = 0.0
    total_residual_var_ema: float = 1.0
