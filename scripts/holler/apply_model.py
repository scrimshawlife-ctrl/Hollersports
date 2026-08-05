#!/usr/bin/env python3
"""Apply calibrated ensemble to odds_records.json → annotated markets (advisory)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.ml.apply import apply_ensemble_to_odds_file  # noqa: E402
from hollersports.strategies.model_probability_edge import ModelProbabilityEdge  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--odds", required=True, help="odds_records.json path")
    p.add_argument("--ensemble", required=True, help="ensemble.json path")
    p.add_argument("--out", default="data/ml/annotated_markets.json")
    p.add_argument("--ev-threshold", type=float, default=0.03)
    p.add_argument(
        "--emit-candidates",
        action="store_true",
        help="Also print MODEL_PROBABILITY_EDGE candidate count (shadow only)",
    )
    args = p.parse_args()
    try:
        payload = apply_ensemble_to_odds_file(
            args.odds,
            args.ensemble,
            out_path=args.out,
            ev_threshold=args.ev_threshold,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "status": "FAIL_CLOSED"}), file=sys.stderr)
        return 1

    summary = {
        "market_count": payload["market_count"],
        "written_to": payload.get("written_to"),
        "packet_hash": payload.get("packet_hash"),
        "ev_positive": sum(
            1 for m in payload["markets"] if m.get("ev_meets_threshold")
        ),
        "capital_authority": False,
        "execution_authority": False,
    }
    if args.emit_candidates:
        strat = ModelProbabilityEdge()
        packet = {
            "run_id": "ML-APPLY",
            "event_id": "SLATE",
            "markets": payload["markets"],
        }
        cands = strat.generate(packet)
        summary["candidate_count"] = len(cands)
        summary["candidates_authority"] = (
            cands[0]["authority"] if cands else None
        )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
