"""PyTorch axial model — skip entire module if torch not installed."""

from pathlib import Path

import pytest

from hollersports.ml.axial_torch import torch_available

pytestmark = pytest.mark.skipif(
    not torch_available(),
    reason="torch not installed (optional [torch] extra)",
)

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures"


def test_train_and_score_axial(tmp_path: Path):
    from hollersports.ml.axial_torch import (
        score_sequence_torch,
        sequences_from_fixture_days,
        train_axial,
    )

    X, y, _yt = sequences_from_fixture_days([FIXTURES / "day001", FIXTURES / "day002"])
    assert len(X) >= 2
    assert len(X) == len(y)

    result = train_axial(
        [FIXTURES / "day001", FIXTURES / "day002"],
        out_dir=tmp_path / "axial",
        epochs=15,
        seed=0,
    )
    assert Path(result["weights_path"]).is_file()
    assert Path(result["meta_path"]).is_file()
    assert result["capital_authority"] is False
    assert 0.0 <= float(result["metrics"]["train_brier"]) <= 1.0

    packet = score_sequence_torch(X[0], model_meta_path=result["meta_path"])
    assert packet["status"] == "COMPUTED"
    assert packet["trained"] is True
    assert packet["kind"] == "axial_torch_v1"
    assert 0.0 < packet["probability"] < 1.0
    assert packet["execution_authority"] is False


def test_untrained_forward_smoke():
    from hollersports.ml.axial_torch import score_sequence_torch

    seq = [[0.5, 0.5, 0.5, 0.5, 0.0, 1.0, 0.0, 0.0, 0.0] for _ in range(4)]
    p = score_sequence_torch(seq, model_meta_path=None)
    assert p["status"] == "UNSUPERVISED_FORWARD"
    assert p["trained"] is False
