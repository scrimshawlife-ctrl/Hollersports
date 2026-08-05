"""Advisory retrain proposals — no auto-train, no authority."""

from pathlib import Path

from hollersports.ml.pipeline import run_train_calibrate
from hollersports.ml.retrain import evaluate_model_on_rows, propose_retrain
from hollersports.ml.train import train_baseline

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures"


def test_propose_retrain_missing_ensemble(tmp_path: Path):
    p = propose_retrain(
        ensemble_path=tmp_path / "nope.json",
        eval_fixture_days=[FIXTURES / "day001"],
    )
    assert p["status"] == "NOT_COMPUTABLE"
    assert p["capital_authority"] is False
    assert p["execution_authority"] is False


def test_propose_retrain_hold_or_suggest(tmp_path: Path):
    if not (FIXTURES / "day001").is_dir():
        return
    result = run_train_calibrate(
        [FIXTURES / "day001", FIXTURES / "day002"],
        None,
        out_dir=tmp_path / "ml",
        prefer_sklearn=False,
        seed=42,
    )
    p = propose_retrain(
        ensemble_path=result["ensemble_path"],
        eval_fixture_days=[FIXTURES / "day001", FIXTURES / "day002", FIXTURES / "day003"],
        min_labeled=5,
    )
    assert p["status"] in {"HOLD", "RETRAIN_SUGGESTED", "NOT_COMPUTABLE"}
    assert p["capital_authority"] is False
    assert p["execution_authority"] is False
    assert p.get("auto_retrain") is False
    assert p["eval_metrics"]["sample_size"] >= 1


def test_evaluate_model_empty():
    m = train_baseline([[0.5] * 9, [0.4] * 9], [1, 0], prefer_sklearn=False)
    out = evaluate_model_on_rows(m, [])
    assert out["status"] == "NOT_COMPUTABLE"
