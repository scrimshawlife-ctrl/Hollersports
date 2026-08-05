"""Model cards + axial temporal stub."""

from pathlib import Path

from hollersports.ml.axial_stub import (
    markets_to_sequence,
    score_sequence,
    smooth_temporal_axis,
)
from hollersports.ml.model_card import build_model_card, write_model_card
from hollersports.ml.pipeline import run_train_calibrate

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures"


def test_smooth_temporal_causal():
    seq = [[1.0, 0.0], [3.0, 2.0], [5.0, 4.0]]
    out = smooth_temporal_axis(seq, window=2)
    assert len(out) == 3
    assert abs(out[0][0] - 1.0) < 1e-9
    assert abs(out[1][0] - 2.0) < 1e-9  # mean(1,3)


def test_score_sequence_empty():
    p = score_sequence([])
    assert p["status"] == "NOT_COMPUTABLE"
    assert p["capital_authority"] is False


def test_score_sequence_from_markets():
    markets = [
        {
            "market_id": "B",
            "market_implied_probability": 0.55,
            "consensus_score": 0.7,
        },
        {
            "market_id": "A",
            "market_implied_probability": 0.45,
            "consensus_score": 0.3,
        },
    ]
    seq = markets_to_sequence(markets)
    assert len(seq) == 2
    # sorted by market_id → A then B
    p = score_sequence(seq)
    assert p["status"] == "COMPUTED"
    assert p["kind"] == "axial_temporal_stub"
    assert p["execution_authority"] is False
    assert len(p["last_features"]) >= 1


def test_model_card_from_train(tmp_path: Path):
    if not (FIXTURES / "day001").is_dir():
        return
    result = run_train_calibrate(
        [FIXTURES / "day001", FIXTURES / "day002"],
        None,
        out_dir=tmp_path / "ml",
        prefer_sklearn=False,
        seed=42,
    )
    assert result.get("model_card_md")
    assert Path(result["model_card_md"]).is_file()
    card = build_model_card(result["ensemble_path"])
    assert card["schema_version"] == "HollerModelCard.v1"
    assert card["capital_authority"] is False
    assert "Model card" in card["markdown"]
    written = write_model_card(result["ensemble_path"], out_dir=tmp_path / "cards")
    assert Path(written["written_md"]).is_file()
