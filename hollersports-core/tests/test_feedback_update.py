from __future__ import annotations
from hollersports_core.schema.expected import ExpectedOutcome
from hollersports_core.schema.result import GameResult
from hollersports_core.schema.state import ModelState
from hollersports_core.feedback.calibrator import compute_metrics
from hollersports_core.feedback.updater import update_state_with_feedback


def test_feedback_updates_priors_in_expected_direction():
    exp = ExpectedOutcome(
        sport="NBA",
        game_id="G1",
        model_version="hs-0.1.0",
        seed=123,
        expected_home_score=110,
        expected_away_score=105,
        expected_total=215,
        expected_spread_home=5,
        sigma_total=10,
        fatigue_weight=1.0,
        tempo_bias=0.0,
        streak_compression=1.0,
    )
    res = GameResult(sport="NBA", game_id="G1", final_home_score=125, final_away_score=110)
    state = ModelState()

    m = compute_metrics(exp, res)
    new_state, priors = update_state_with_feedback(state, exp, m)

    assert new_state.tempo_bias >= state.tempo_bias  # underpredicted total -> tempo up
    assert new_state.fatigue_weight >= state.fatigue_weight  # higher surprise -> fatigue up
    assert new_state.streak_compression >= state.streak_compression
