#!/usr/bin/env python3
"""Run multi-fixture operator days and emit a calibration suite receipt.

Advisory only — no real money. Exit non-zero on authority leaks or invariance fails.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from hollersports.pipelines.operator_day import run_operator_day
from hollersports.runes.calibration_evaluator import evaluate_calibration
from hollersports.schemas.hashing import packet_hash

DEFAULT_FIXTURES = ("day001", "day002")


def _run_fixture(fixture: Path, data_root: Path) -> dict:
    out = run_operator_day(fixture, data_root=data_root)
    entries = (out.get("settlements") or {}).get("entries") or []
    cal = evaluate_calibration(entries, allow_forecast_weighting=True)
    core = {
        "ingest_status": out["ingest"]["status"],
        "candidate_count": out["competition"].get("candidate_count"),
        "model_edge_enabled": out["competition"].get("model_edge_enabled"),
        "promotion_status": out["promotion"]["status"],
        "calibration_status": cal["status"],
        "calibration_sample": cal["sample_size"],
        "model_edge_allowed": cal["model_edge_allowed"],
    }
    for key in ("ingest", "competition", "dashboard", "performance", "promotion"):
        pkt = out[key]
        if pkt.get("capital_authority") is True or pkt.get("execution_authority") is True:
            raise RuntimeError(f"authority leak in {key} for {fixture.name}")
        if pkt.get("mode") == "LIVE_APPROVED":
            raise RuntimeError(f"LIVE_APPROVED in {key} for {fixture.name}")
    if out["dashboard"]["authority"] != "PROJECTION_ONLY":
        raise RuntimeError(f"dashboard not PROJECTION_ONLY for {fixture.name}")
    return {
        "fixture": fixture.name,
        "core": core,
        "core_hash": packet_hash(core),
        "calibration": {
            "status": cal["status"],
            "reliability_status": cal["reliability_status"],
            "sample_size": cal["sample_size"],
            "hit_rate": cal["hit_rate"],
            "sim_roi": cal["sim_roi"],
            "model_edge_allowed": cal["model_edge_allowed"],
            "failed_gates": cal["failed_gates"],
            "packet_hash": cal["packet_hash"],
        },
        "capital_authority": False,
        "execution_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=Path("fixtures"),
        help="Directory containing fixture day folders",
    )
    parser.add_argument(
        "--fixtures",
        nargs="*",
        default=list(DEFAULT_FIXTURES),
        help="Fixture day names (default: day001 day002)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/calibration_suite.last.json"),
        help="Receipt path",
    )
    parser.add_argument(
        "--invariance-runs",
        type=int,
        default=3,
        help="Repeats per fixture for hash invariance (default 3)",
    )
    args = parser.parse_args()

    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="holler-cal-") as tmp:
        root = Path(tmp)
        for name in args.fixtures:
            day = args.fixtures_root / name
            if not day.is_dir():
                print(f"fixture missing: {day}", file=sys.stderr)
                return 2
            hashes: list[str] = []
            last: dict | None = None
            for i in range(max(1, args.invariance_runs)):
                last = _run_fixture(day, root / name / f"r{i}")
                hashes.append(str(last["core_hash"]))
            assert last is not None
            if len(set(hashes)) != 1:
                print(f"invariance fail {name}: {hashes}", file=sys.stderr)
                return 3
            last["invariance_runs"] = len(hashes)
            last["invariance_pass"] = True
            results.append(last)

    receipt = {
        "schema_version": "HollerCalibrationSuiteReceipt.v1",
        "mode": "PAPER_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "fixtures": results,
        "fixture_count": len(results),
        "seals": {
            "CAPITAL_AUTHORITY": False,
            "EXECUTION_AUTHORITY": False,
            "LIVE_BOOKS": False,
            "MODE": "PAPER_ONLY",
        },
    }
    receipt["receipt_hash"] = packet_hash(
        {k: v for k, v in receipt.items() if k != "receipt_hash"}
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "OK",
                "fixture_count": len(results),
                "receipt_hash": receipt["receipt_hash"],
                "out": str(args.out),
                "calibration": [
                    {
                        "fixture": r["fixture"],
                        "status": r["calibration"]["status"],
                        "sample": r["calibration"]["sample_size"],
                        "model_edge_allowed": r["calibration"]["model_edge_allowed"],
                    }
                    for r in results
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
