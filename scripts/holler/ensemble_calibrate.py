#!/usr/bin/env python3
"""Re-run temperature calibration given an existing model + validation fixture days.

Prefer ``train_gbm.py`` which trains and calibrates in one shot. This script is for
re-calibrating after new settled labels arrive.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.ml.calibrate import (  # noqa: E402
    build_ensemble_artifact,
    calibrate_temperature,
    save_ensemble,
)
from hollersports.ml.features import build_feature_rows, features_data_hash
from hollersports.ml.train import load_model, predict_proba


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True, help="Path to baseline model JSON")
    p.add_argument("--val-days", nargs="+", required=True)
    p.add_argument("--out", default="data/ml/ensemble.json")
    args = p.parse_args()

    model = load_model(args.model)
    val_rows = build_feature_rows(args.val_days, require_labels=True)
    if not val_rows:
        print(json.dumps({"error": "no labeled val rows"}), file=sys.stderr)
        return 1
    probs = [predict_proba(model, r["x"]) for r in val_rows]
    y = [int(r["y"]) for r in val_rows]
    cal = calibrate_temperature(probs, y)
    data_hash = features_data_hash(val_rows)
    model_id = str(model.get("model_id") or Path(args.model).stem)
    art = build_ensemble_artifact(
        base_model_path=Path(args.model).name,
        base_model_id=model_id,
        temperature=float(cal["temperature"]),
        metrics=cal,
        data_hash=data_hash,
    )
    # Prefer absolute path in ensemble for re-calibrate when model lives elsewhere
    art["models"][0]["path"] = str(Path(args.model).resolve())
    path = save_ensemble(art, args.out)
    print(json.dumps({"ensemble_path": str(path), **cal, "ensemble_id": art["ensemble_id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
