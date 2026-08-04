"""MODEL_PROBABILITY_EDGE — gated deterministic model edge (no invent)."""

from hollersports.strategies.model_probability_edge import (
    MODEL_EDGE_THRESHOLD,
    ModelProbabilityEdge,
)


def _packet(markets: list[dict]) -> dict:
    return {
        "schema_version": "MarketIngestionPacket.v1",
        "status": "INGESTED",
        "run_id": "R-MODEL",
        "event_id": "E1",
        "markets": markets,
        "authority": "SHADOW_ONLY",
    }


def test_generate_empty_without_model_fields():
    strat = ModelProbabilityEdge()
    out = strat.generate(
        _packet(
            [
                {
                    "market_id": "M1",
                    "selection": "HOME_ML",
                    "consensus_score": 0.8,
                }
            ]
        )
    )
    assert out == []


def test_generate_deterministic_when_edge_above_threshold():
    strat = ModelProbabilityEdge()
    # model 0.58 vs implied 0.50 → edge 0.08 >= 0.03
    out = strat.generate(
        _packet(
            [
                {
                    "market_id": "M1",
                    "selection": "HOME_ML",
                    "model_probability": 0.58,
                    "market_implied_probability": 0.50,
                }
            ]
        )
    )
    assert len(out) == 1
    c = out[0]
    assert c["strategy_id"] == "MODEL_PROBABILITY_EDGE"
    assert c["strategy_family"] == "MODEL"
    assert c["authority"] == "SHADOW_ONLY"
    assert c["capital_authority"] is False
    assert c["execution_authority"] is False
    assert c["market_id"] == "M1"
    assert c["selection"] == "HOME_ML"
    edge = 0.58 - 0.50
    expected_score = min(1.0, max(0.0, edge / 0.20))
    assert abs(c["score"] - expected_score) < 1e-9
    assert abs(c["confidence"] - 0.58) < 1e-9
    assert c["features"]["edge"] == edge
    assert c["features"]["threshold"] == MODEL_EDGE_THRESHOLD

    # Determinism: same inputs → same outputs
    out2 = strat.generate(
        _packet(
            [
                {
                    "market_id": "M1",
                    "selection": "HOME_ML",
                    "model_probability": 0.58,
                    "market_implied_probability": 0.50,
                }
            ]
        )
    )
    assert out2 == out


def test_generate_skips_below_threshold():
    strat = ModelProbabilityEdge()
    # edge 0.01 < 0.03
    out = strat.generate(
        _packet(
            [
                {
                    "market_id": "M1",
                    "selection": "HOME_ML",
                    "model_probability": 0.51,
                    "implied_probability": 0.50,
                }
            ]
        )
    )
    assert out == []


def test_candidates_always_shadow_only():
    strat = ModelProbabilityEdge()
    out = strat.generate(
        _packet(
            [
                {
                    "market_id": "M2",
                    "selection": "AWAY_ML",
                    "model_probability": 0.70,
                    "market_implied_probability": 0.55,
                    "model_side": "AWAY_ML",
                }
            ]
        )
    )
    assert len(out) == 1
    assert out[0]["authority"] == "SHADOW_ONLY"
    assert out[0]["capital_authority"] is False
    assert out[0]["execution_authority"] is False


def test_invalid_model_probability_skipped():
    strat = ModelProbabilityEdge()
    out = strat.generate(
        _packet(
            [
                {
                    "market_id": "M1",
                    "selection": "HOME_ML",
                    "model_probability": "not-a-number",
                    "market_implied_probability": 0.5,
                },
                {
                    "market_id": "M2",
                    "selection": "HOME_ML",
                    "model_probability": 0.0,  # not in (0,1)
                    "market_implied_probability": 0.5,
                },
                {
                    "market_id": "M3",
                    "selection": "HOME_ML",
                    "model_probability": 1.0,  # not in (0,1)
                    "market_implied_probability": 0.5,
                },
            ]
        )
    )
    assert out == []
