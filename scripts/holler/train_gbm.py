#!/usr/bin/env python3
"""Train baseline (logistic L2 default; sklearn HGB with --sklearn) on fixture days."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.ml.pipeline import run_train_calibrate  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("train_days", nargs="+", help="Labeled fixture days for training")
    p.add_argument(
        "--val-days",
        nargs="*",
        default=None,
        help="Optional validation fixture days (else holdout from train)",
    )
    p.add_argument("--out-dir", default="data/ml", help="Artifact directory")
    p.add_argument(
        "--sklearn",
        action="store_true",
        help="Prefer sklearn HistGradientBoosting when installed",
    )
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    try:
        result = run_train_calibrate(
            args.train_days,
            args.val_days,
            out_dir=args.out_dir,
            prefer_sklearn=args.sklearn,
            seed=args.seed,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "status": "FAIL"}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
