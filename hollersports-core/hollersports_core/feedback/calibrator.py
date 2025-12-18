from __future__ import annotations
import numpy as np
from ..schema.expected import ExpectedOutcome
from ..schema.result import GameResult
from ..schema.feedback import FeedbackMetrics


def compute_metrics(exp: ExpectedOutcome, res: GameResult) -> FeedbackMetrics:
    final_total = res.final_home_score + res.final_away_score
    final_spread_home = res.final_home_score - res.final_away_score

    residual_total = final_total - exp.expected_total
    residual_spread_home = final_spread_home - exp.expected_spread_home

    # Normalize total residual by predicted sigma_total (guarded by schema gt 0)
    z_total = float(residual_total / exp.sigma_total)

    abs_z = float(abs(z_total))

    # Surprise: smooth + cap (economical, stable)
    # maps abs_z in [0, +inf) to [0, 3) approximately.
    surprise = float(3.0 * (1.0 - np.exp(-abs_z)))

    return FeedbackMetrics(
        game_id=exp.game_id,
        residual_total=float(residual_total),
        residual_spread_home=float(residual_spread_home),
        z_total=z_total,
        abs_z_total=abs_z,
        surprise=surprise,
    )
