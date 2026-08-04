#!/usr/bin/env python3
"""Multi-fixture paper backfill into a shared data root (calibration bank).

Advisory only — accumulates settled simulation outcomes for advice quality.
Never places bets or moves capital.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hollersports.pipelines.operator_day import run_operator_day
from hollersports.runes.calibration_evaluator import evaluate_calibration
from hollersports.paper.settlement_history import read_settlement_history
from hollersports.schemas.hashing import packet_hash

DEFAULT_FIXTURES = ("day001", "day002")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=Path("fixtures"),
    )
    parser.add_argument(
        "--fixtures",
        nargs="*",
        default=list(DEFAULT_FIXTURES),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data/backfill"),
        help="Shared root for cumulative ledgers (default: data/backfill)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=4,
        help="How many times to run each fixture (grows sample; default 4)",
    )
    parser.add_argument(
        "--paper-top-n",
        type=int,
        default=50,
        help="Paper candidate cap per run (default 50 for sample growth)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/backfill_calibration.last.json"),
    )
    args = parser.parse_args()

    args.data_root.mkdir(parents=True, exist_ok=True)
    runs: list[dict] = []

    for rep in range(max(1, args.repeats)):
        for name in args.fixtures:
            day = args.fixtures_root / name
            if not day.is_dir():
                print(f"fixture missing: {day}", file=sys.stderr)
                return 2
            # Isolate paper ledger path per rep but share data_root settlement bank
            # via accumulate_settlements into data_root/ledgers/
            out = run_operator_day(
                day,
                data_root=args.data_root / f"run-{name}-r{rep}",
                paper_top_n=args.paper_top_n,
                accumulate_settlements=False,
            )
            # Re-append into shared bank under data_root
            from hollersports.paper.settlement_history import append_settlement_history
            from hollersports.paper.reliability_ledger import (
                record_reliability_from_settlements,
            )

            entries = (out.get("settlements") or {}).get("entries") or []
            append_settlement_history(
                args.data_root,
                entries,
                run_id=str((out.get("ingest") or {}).get("run_id") or name),
                fixture=name,
            )
            record_reliability_from_settlements(args.data_root, entries)
            runs.append(
                {
                    "fixture": name,
                    "repeat": rep,
                    "settled": len(
                        [
                            e
                            for e in entries
                            if str(e.get("status") or "").upper()
                            in {"WIN", "LOSS", "PUSH", "VOID"}
                        ]
                    ),
                    "candidate_count": (out.get("competition") or {}).get(
                        "candidate_count"
                    ),
                }
            )

    hist = read_settlement_history(data_root=args.data_root, settled_only=True)
    cal = evaluate_calibration(hist, allow_forecast_weighting=True)

    receipt = {
        "schema_version": "HollerBackfillReceipt.v1",
        "mode": "PAPER_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "data_root": str(args.data_root),
        "repeats": args.repeats,
        "paper_top_n": args.paper_top_n,
        "fixtures": list(args.fixtures),
        "runs": runs,
        "cumulative_sample": len(hist),
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
        "seals": {
            "CAPITAL_AUTHORITY": False,
            "EXECUTION_AUTHORITY": False,
            "LIVE_BOOKS": False,
        },
    }
    receipt["receipt_hash"] = packet_hash(
        {k: v for k, v in receipt.items() if k != "receipt_hash"}
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": "OK",
                "cumulative_sample": len(hist),
                "calibration_status": cal["status"],
                "model_edge_allowed": cal["model_edge_allowed"],
                "out": str(args.out),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
