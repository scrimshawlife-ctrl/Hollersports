#!/usr/bin/env python3
"""E2E: train on day001+day002, apply on day003, emit evidence JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.ml.apply import apply_ensemble_to_odds_file  # noqa: E402
from hollersports.ml.pipeline import run_train_calibrate  # noqa: E402
from hollersports.strategies.model_probability_edge import ModelProbabilityEdge  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixtures-root", default=str(_REPO / "fixtures"))
    p.add_argument("--out-dir", default=str(_REPO / "data" / "ml" / "e2e"))
    p.add_argument(
        "--evidence",
        default=str(_REPO / "docs" / "evidence" / "ml_pipeline_e2e.last.json"),
    )
    args = p.parse_args()
    root = Path(args.fixtures_root)
    train = [root / "day001", root / "day002"]
    for d in train:
        if not d.is_dir():
            print(json.dumps({"error": f"missing {d}"}), file=sys.stderr)
            return 1
    day003 = root / "day003"
    if not day003.is_dir():
        print(json.dumps({"error": f"missing {day003}"}), file=sys.stderr)
        return 1

    train_result = run_train_calibrate(
        train,
        None,
        out_dir=args.out_dir,
        prefer_sklearn=False,
        seed=42,
    )
    annotated = apply_ensemble_to_odds_file(
        day003 / "odds_records.json",
        train_result["ensemble_path"],
        out_path=Path(args.out_dir) / "day003_annotated.json",
    )
    strat = ModelProbabilityEdge()
    cands = strat.generate(
        {
            "run_id": "ML-E2E",
            "event_id": "day003",
            "markets": annotated["markets"],
        }
    )
    edges = [
        {
            "market_id": m.get("market_id"),
            "model_probability": m.get("model_probability"),
            "model_probability_raw": m.get("model_probability_raw"),
            "implied": m.get("market_implied_probability"),
            "edge": m.get("model_edge"),
            "edge_raw": m.get("model_edge_raw"),
            "ev": m.get("expected_value"),
        }
        for m in annotated["markets"]
    ]
    evidence = {
        "schema_version": "HollerMlE2EEvidence.v1",
        "train": train_result,
        "apply": {
            "market_count": annotated["market_count"],
            "packet_hash": annotated["packet_hash"],
            "ev_positive": sum(
                1 for m in annotated["markets"] if m.get("ev_meets_threshold")
            ),
            "edges": edges,
        },
        "candidates": {
            "count": len(cands),
            "strategy_id": "MODEL_PROBABILITY_EDGE",
            "authority": "SHADOW_ONLY",
            "sample": [
                {
                    "market_id": c.get("market_id"),
                    "score": c.get("score"),
                    "edge": (c.get("features") or {}).get("edge"),
                }
                for c in cands[:5]
            ],
        },
        "capital_authority": False,
        "execution_authority": False,
        "status": "ADVISORY_ONLY",
    }
    ep = Path(args.evidence)
    ep.parent.mkdir(parents=True, exist_ok=True)
    ep.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    # Fixture bank is small but raw model edge should still clear strategy threshold.
    if len(cands) < 1:
        print(
            json.dumps(
                {
                    "error": "expected >=1 MODEL_PROBABILITY_EDGE candidates on day003",
                    "temperature": train_result.get("metrics", {}).get("temperature"),
                }
            ),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
