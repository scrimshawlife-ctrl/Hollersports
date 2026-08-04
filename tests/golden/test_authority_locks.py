from pathlib import Path

from hollersports.pipelines.operator_day import run_operator_day
from hollersports.governance.authority import assert_no_live_capital


def test_no_live_flags_in_operator_day(tmp_path: Path):
    out = run_operator_day(Path("fixtures/day001"), data_root=tmp_path)
    for key in ("ingest", "competition", "dashboard", "performance", "promotion"):
        assert_no_live_capital(out[key] if isinstance(out[key], dict) else {})
    for c in out["competition"].get("candidates", []):
        assert_no_live_capital(c)
        assert c.get("mode") != "LIVE_APPROVED"
