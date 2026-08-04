#!/usr/bin/env python3
"""Fixture operator-day smoke for production readiness evidence."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from hollersports.pipelines.operator_day import run_operator_day
from hollersports.schemas.hashing import packet_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("fixtures/day001"),
        help="Fixture directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/smoke_operator_day.last.json"),
        help="Evidence receipt path",
    )
    args = parser.parse_args()

    if not args.fixture.is_dir():
        print(f"fixture missing: {args.fixture}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="holler-smoke-") as tmp:
        out = run_operator_day(args.fixture, data_root=Path(tmp))

    core = {
        "ingest_status": out["ingest"]["status"],
        "candidate_count": out["competition"].get("candidate_count"),
        "promotion_status": out["promotion"]["status"],
        "dashboard_authority": out["dashboard"]["authority"],
        "capital_authority": out["dashboard"].get("capital_authority"),
        "execution_authority": out["dashboard"].get("execution_authority"),
    }
    core_hash = packet_hash(core)

    for key in ("ingest", "competition", "dashboard", "performance", "promotion"):
        pkt = out[key]
        if pkt.get("capital_authority") is True or pkt.get("execution_authority") is True:
            print(f"authority leak in {key}", file=sys.stderr)
            return 3
        if pkt.get("mode") == "LIVE_APPROVED":
            print(f"LIVE_APPROVED in {key}", file=sys.stderr)
            return 3

    if out["dashboard"]["authority"] != "PROJECTION_ONLY":
        print("dashboard not PROJECTION_ONLY", file=sys.stderr)
        return 3

    receipt = {
        "schema_version": "HollerSmokeReceipt.v1",
        "mode": "PAPER_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "fixture": str(args.fixture),
        "core": core,
        "core_hash": core_hash,
        "seals": {
            "CAPITAL_AUTHORITY": False,
            "EXECUTION_AUTHORITY": False,
            "LIVE_BOOKS": False,
            "MODE": "PAPER_ONLY",
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "core_hash": core_hash, "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
