#!/usr/bin/env python3
"""Annotate a fixture day with ML ensemble and run strategy competition (advisory).

Requires an existing ensemble (train with train_gbm / ml_e2e first) or --train-days.
Model edge is loaded only when --allow-model-edge is set (explicit operator opt-in
for this offline demo; production still uses calibration ladder via API).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.ml.apply import apply_ensemble_to_markets  # noqa: E402
from hollersports.ml.pipeline import run_train_calibrate  # noqa: E402
from hollersports.pipelines.market_ingestion import run_market_ingestion  # noqa: E402
from hollersports.pipelines.strategy_competition import run_strategy_competition  # noqa: E402
from hollersports.sources.fixture_adapter import load_fixture_day  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--fixture-day",
        default=str(_REPO / "fixtures" / "day003"),
        help="Fixture day directory to annotate + compete",
    )
    p.add_argument(
        "--ensemble",
        default=None,
        help="Path to ensemble.json (required unless --train-days given)",
    )
    p.add_argument(
        "--train-days",
        nargs="*",
        default=None,
        help="If set, train+calibrate into --out-dir before compete",
    )
    p.add_argument("--out-dir", default=str(_REPO / "data" / "ml" / "compete"))
    p.add_argument(
        "--allow-model-edge",
        action="store_true",
        help="Opt-in MODEL_PROBABILITY_EDGE for this offline run (SHADOW_ONLY)",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Evidence JSON path (default: out-dir/ml_compete.last.json)",
    )
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ensemble_path = args.ensemble

    train_meta = None
    if args.train_days:
        train_meta = run_train_calibrate(
            args.train_days,
            None,
            out_dir=out_dir / "train",
            prefer_sklearn=False,
            seed=42,
        )
        ensemble_path = train_meta["ensemble_path"]
    if not ensemble_path:
        print(
            json.dumps({"error": "provide --ensemble or --train-days"}),
            file=sys.stderr,
        )
        return 1

    day_path = Path(args.fixture_day)
    day = load_fixture_day(day_path)
    ingest_payload = day["ingest_payload"]
    raw_markets = list(ingest_payload.get("payload", {}).get("markets") or [])
    scored = apply_ensemble_to_markets(raw_markets, ensemble_path)
    # Replace markets with ML-annotated copies (fail-closed: keep unscored raw only if score fails)
    by_id = {str(m.get("market_id")): m for m in scored}
    merged = []
    for m in raw_markets:
        mid = str(m.get("market_id") or "")
        merged.append(by_id.get(mid) or m)
    ingest_payload = dict(ingest_payload)
    payload = dict(ingest_payload.get("payload") or {})
    payload["markets"] = merged
    ingest_payload["payload"] = payload
    refs = dict(ingest_payload.get("source_refs") or {})
    refs["ml_ensemble"] = str(ensemble_path)
    refs["ml_annotated"] = True
    ingest_payload["source_refs"] = refs

    ingest = run_market_ingestion(ingest_payload)
    calibration = None
    if args.allow_model_edge:
        # Explicit offline demo gate — not a production reliability claim.
        calibration = {
            "model_edge_allowed": True,
            "allow_forecast_weighting": True,
            "reliability_status": "RELIABLE",
            "reason": "ml_compete_day_explicit_opt_in",
            "capital_authority": False,
            "execution_authority": False,
        }
    competition = run_strategy_competition(ingest, calibration=calibration)

    model_cands = [
        c
        for c in (competition.get("candidates") or [])
        if isinstance(c, dict) and c.get("strategy_id") == "MODEL_PROBABILITY_EDGE"
    ]
    evidence = {
        "schema_version": "HollerMlCompeteDay.v1",
        "fixture_day": str(day_path),
        "ensemble_path": str(ensemble_path),
        "train": train_meta,
        "annotated_markets": len(scored),
        "ingest_status": ingest.get("status"),
        "model_edge_enabled": competition.get("model_edge_enabled"),
        "candidate_count": len(competition.get("candidates") or []),
        "model_edge_candidate_count": len(model_cands),
        "top_model_edges": [
            {
                "market_id": c.get("market_id"),
                "selection": c.get("selection"),
                "score": c.get("score"),
                "confidence": c.get("confidence"),
                "edge": (c.get("features") or {}).get("edge"),
            }
            for c in sorted(
                model_cands,
                key=lambda x: float(x.get("score") or 0),
                reverse=True,
            )[:5]
        ],
        "capital_authority": False,
        "execution_authority": False,
        "status": "ADVISORY_ONLY",
    }
    out_path = Path(args.out or (out_dir / "ml_compete.last.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
