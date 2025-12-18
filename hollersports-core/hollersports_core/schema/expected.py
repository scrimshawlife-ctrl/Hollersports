from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal

Sport = Literal["NBA","NHL","NFL","MLB","WNBA","EPL","OTHER"]


class ExpectedOutcome(BaseModel):
    sport: Sport
    game_id: str
    model_version: str
    seed: int = Field(..., ge=0, le=2_147_483_647)

    # Core expected values
    expected_home_score: float
    expected_away_score: float
    expected_total: float
    expected_spread_home: float  # home - away

    # Model uncertainty estimate (from sim): stdev of total points
    sigma_total: float = Field(..., gt=0)

    # Priors snapshot at time of prediction (for audit)
    fatigue_weight: float
    tempo_bias: float
    streak_compression: float
