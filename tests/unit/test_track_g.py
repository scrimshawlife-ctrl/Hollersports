"""Track G: sequence store, CRPS, larger arch presets."""

from pathlib import Path

import pytest

from hollersports.ml.crps import crps_categorical, expected_bin
from hollersports.ml.axial_torch import torch_available
from hollersports.sources.sequence_store import (
    append_poll,
    load_fixture_sequences,
    sequences_by_line_key,
    write_fixture_sequences,
)

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures"


def test_crps_categorical_perfect():
    # certainty on bin 2
    probs = [0.0, 0.0, 1.0, 0.0]
    assert crps_categorical(probs, 2) == 0.0
    assert expected_bin(probs) == 2.0


def test_sequence_store_append_and_load(tmp_path: Path):
    markets = [
        {
            "event_id": "E1",
            "market_type": "MONEYLINE",
            "selection": "HOME_ML",
            "market_id": "M1",
            "price": -150,
            "consensus_score": 0.7,
        }
    ]
    r1 = append_poll(tmp_path, markets, poll_id="p1", fetched_at=1.0)
    assert r1["rows_written"] == 1
    r2 = append_poll(
        tmp_path,
        [
            {
                **markets[0],
                "price": -160,
                "consensus_score": 0.72,
            }
        ],
        poll_id="p2",
        fetched_at=2.0,
    )
    assert r2["rows_written"] == 1
    seqs = sequences_by_line_key(tmp_path, min_len=2)
    assert len(seqs) >= 1
    key = next(iter(seqs))
    assert len(seqs[key]) == 2


def test_fixture_sequences_file():
    path = FIXTURES / "sequences" / "synthetic_totals.json"
    items = load_fixture_sequences(path)
    assert len(items) >= 4
    assert "x_seq" in items[0]


@pytest.mark.skipif(not torch_available(), reason="torch optional")
def test_train_transformer_dist(tmp_path: Path):
    from hollersports.ml.axial_torch import score_sequence_torch, train_axial

    result = train_axial(
        [FIXTURES / "day001", FIXTURES / "day002"],
        out_dir=tmp_path / "axial",
        epochs=12,
        seed=0,
        arch_preset="transformer_dist",
        fixture_sequence_path=FIXTURES / "sequences" / "synthetic_totals.json",
    )
    assert result["arch"] == "transformer"
    assert result["distributional"] is True
    assert result.get("metrics", {}).get("train_crps") is not None
    assert result.get("model_card_md")
    packet = score_sequence_torch(
        [[0.5] * 9, [0.55] * 9, [0.6] * 9],
        model_meta_path=result["meta_path"],
    )
    assert packet["trained"] is True
    assert packet.get("total_probs") is not None
    assert len(packet["total_probs"]) == 11
    assert packet["expected_total"] is not None


@pytest.mark.skipif(not torch_available(), reason="torch optional")
def test_train_axial_large(tmp_path: Path):
    from hollersports.ml.axial_torch import train_axial

    result = train_axial(
        [FIXTURES / "day001"],
        out_dir=tmp_path / "axial_l",
        epochs=8,
        seed=1,
        arch_preset="axial_large",
        fixture_sequence_path=FIXTURES / "sequences" / "synthetic_totals.json",
    )
    assert result["d_model"] == 64
    assert result["n_layers"] == 4
