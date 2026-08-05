from pathlib import Path

from hollersports.pipelines.operator_day import run_operator_day
from hollersports.schemas.hashing import packet_hash


def test_twelve_run_same_hashes(tmp_path: Path):
    hashes = []
    for i in range(12):
        out = run_operator_day(Path("fixtures/day001"), data_root=tmp_path / f"r{i}")
        # hash core deterministic packets (exclude wall-clock if any — strip timestamps if present)
        core = {
            "ingest_status": out["ingest"]["status"],
            "candidates": out["competition"].get("candidates", []),
            "promotion_status": out["promotion"]["status"],
        }
        hashes.append(packet_hash(core))
    assert len(set(hashes)) == 1
