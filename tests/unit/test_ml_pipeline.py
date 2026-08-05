"""Track F ML pipeline — pure-Python path (no sklearn required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hollersports.ml.apply import apply_ensemble_to_markets, apply_ensemble_to_odds_file
from hollersports.ml.calibrate import apply_temperature, calibrate_temperature
from hollersports.ml.ev import annotate_ev, compute_ev
from hollersports.ml.features import (
    FEATURE_NAMES,
    american_to_decimal,
    american_to_implied,
    build_feature_rows,
    extract_feature_vector,
)
from hollersports.ml.pipeline import run_train_calibrate
from hollersports.ml.train import predict_proba, train_baseline
from hollersports.strategies.model_probability_edge import ModelProbabilityEdge

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures"


def test_american_odds_helpers():
    assert abs(american_to_implied(-110) - (110 / 210)) < 1e-9
    assert abs(american_to_implied(100) - 0.5) < 1e-9
    assert american_to_implied(0) is None
    assert abs(american_to_decimal(-110) - (1 + 100 / 110)) < 1e-9
    assert abs(american_to_decimal(150) - 2.5) < 1e-9


def test_extract_features_fail_closed_on_bad_price():
    assert extract_feature_vector({"selection": "HOME_ML"}) is None
    feat = extract_feature_vector(
        {
            "selection": "HOME_ML",
            "price": -150,
            "consensus_score": 0.7,
        }
    )
    assert feat is not None
    assert set(feat.keys()) == set(FEATURE_NAMES)
    assert 0.0 < feat["implied_probability"] < 1.0
    assert feat["is_home"] == 1.0
    assert feat["sentiment_score"] == 0.0
    assert feat["odds_delta"] == 0.0


def test_build_feature_rows_from_fixtures():
    rows = build_feature_rows([FIXTURES / "day001"], require_labels=True)
    assert len(rows) >= 2
    assert all("x" in r and len(r["x"]) == len(FEATURE_NAMES) for r in rows)
    assert all(r["y"] in (0, 1) for r in rows)


def test_train_predict_deterministic():
    X = [
        [0.55, 0.7, 0.6, 0.5, 0.02, 1.0, -0.5, 0.0, 0.0],
        [0.45, 0.3, 0.4, 0.5, -0.01, 0.0, 0.4, 0.0, 0.0],
        [0.60, 0.8, 0.7, 0.55, 0.03, 1.0, -0.6, 0.0, 0.0],
        [0.40, 0.2, 0.3, 0.45, -0.02, 0.0, 0.5, 0.0, 0.0],
    ]
    y = [1, 0, 1, 0]
    m1 = train_baseline(X, y, prefer_sklearn=False, seed=42)
    m2 = train_baseline(X, y, prefer_sklearn=False, seed=42)
    assert m1["weights"] == m2["weights"]
    assert m1["bias"] == m2["bias"]
    p = predict_proba(m1, X[0])
    assert 0.0 < p < 1.0
    assert abs(predict_proba(m2, X[0]) - p) < 1e-12


def test_temperature_calibration_improves_or_equals_grid():
    probs = [0.9, 0.8, 0.2, 0.1]
    y = [1, 1, 0, 0]
    # Small n → identity temperature (noise guard)
    cal_small = calibrate_temperature(probs, y)
    assert cal_small["temperature"] == 1.0
    assert cal_small["temperature_source"] == "identity_small_val"

    # Large n → grid search allowed
    probs_big = probs * 3
    y_big = y * 3
    cal = calibrate_temperature(probs_big, y_big, min_val_for_temperature=8)
    assert cal["temperature"] > 0
    assert cal["temperature"] <= 2.5
    assert "val_nll" in cal
    assert 0.0 < apply_temperature(0.9, cal["temperature"]) < 1.0


def test_compute_ev():
    # p=0.6, +100 decimal 2.0 → EV = 0.2
    assert abs(compute_ev(0.6, 100) - 0.2) < 1e-9
    block = annotate_ev(model_probability=0.6, american_price=100, market_implied=0.5)
    assert block["capital_authority"] is False
    assert block["execution_authority"] is False
    assert block["status"] == "ADVISORY_ONLY"
    assert block["ev_meets_threshold"] is True


def test_pipeline_e2e_day003(tmp_path: Path):
    if not (FIXTURES / "day001").is_dir():
        pytest.skip("fixtures missing")
    result = run_train_calibrate(
        [FIXTURES / "day001", FIXTURES / "day002"],
        None,
        out_dir=tmp_path / "ml",
        prefer_sklearn=False,
        seed=42,
    )
    assert Path(result["ensemble_path"]).is_file()
    assert Path(result["model_path"]).is_file()
    assert result["capital_authority"] is False
    assert result["execution_authority"] is False

    payload = apply_ensemble_to_odds_file(
        FIXTURES / "day003" / "odds_records.json",
        result["ensemble_path"],
        out_path=tmp_path / "annotated.json",
    )
    assert payload["market_count"] >= 1
    m0 = payload["markets"][0]
    assert 0.0 < m0["model_probability"] < 1.0
    assert m0["ml_provenance"]["capital_authority"] is False
    assert m0["ml_provenance"]["execution_authority"] is False
    assert "ensemble_id" in m0["ml_provenance"]

    # Fail closed: missing ensemble
    with pytest.raises(FileNotFoundError):
        apply_ensemble_to_markets(
            payload["markets"][:1],
            tmp_path / "nope.json",
        )

    strat = ModelProbabilityEdge()
    cands = strat.generate(
        {
            "run_id": "T",
            "event_id": "E",
            "markets": payload["markets"],
        }
    )
    # Small-n identity temperature preserves raw edge → candidates fire on day003
    assert len(cands) >= 1
    for c in cands:
        assert c["authority"] == "SHADOW_ONLY"
        assert c["capital_authority"] is False
        assert c["execution_authority"] is False
        assert c["strategy_id"] == "MODEL_PROBABILITY_EDGE"

    # Second run same seed → same train brier path stability
    result2 = run_train_calibrate(
        [FIXTURES / "day001", FIXTURES / "day002"],
        None,
        out_dir=tmp_path / "ml2",
        prefer_sklearn=False,
        seed=42,
    )
    assert result2["metrics"]["train_brier"] == result["metrics"]["train_brier"]
    assert result["metrics"]["temperature"] == 1.0
    assert result["metrics"].get("temperature_source") in {
        "identity_small_val",
        "identity_train_eq_val",
    }


def test_fail_closed_no_invent_without_features():
    from hollersports.ml.apply import score_market
    from hollersports.ml.train import train_logistic_l2

    markets = [{"market_id": "X", "selection": "HOME_ML"}]  # no price
    X = [[0.5] * len(FEATURE_NAMES), [0.4] * len(FEATURE_NAMES)]
    y = [1, 0]
    model = train_logistic_l2(X, y, epochs=50)
    scored = score_market(
        markets[0],
        model=model,
        temperature=1.0,
        ensemble_id="e",
        model_id="t",
        data_hash="d",
        artifact_hash="a",
    )
    assert scored is None
