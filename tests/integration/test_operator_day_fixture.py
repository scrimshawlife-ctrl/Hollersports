from pathlib import Path

from hollersports.pipelines.operator_day import run_operator_day


def test_closed_loop_fixture(tmp_path: Path):
    out = run_operator_day(Path("fixtures/day001"), data_root=tmp_path)
    assert out["ingest"]["status"] == "INGESTED"
    assert out["competition"]["status"] == "COMPUTED"
    assert out["dashboard"]["authority"] == "PROJECTION_ONLY"
    assert out["dashboard"].get("capital_authority") is False
    assert "Place bet" not in str(out)
