from __future__ import annotations
from pydantic import BaseModel
from typing import Literal
from .expected import Sport


class GameResult(BaseModel):
    sport: Sport
    game_id: str
    final_home_score: float
    final_away_score: float
    status: Literal["FINAL"] = "FINAL"
