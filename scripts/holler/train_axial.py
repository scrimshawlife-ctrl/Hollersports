#!/usr/bin/env python3
"""Train PyTorch axial model on fixture days (requires [torch] extra)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("train_days", nargs="+", help="Fixture day dirs")
    p.add_argument("--out-dir", default="data/ml/axial")
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument(
        "--arch",
        default="axial_small",
        choices=["axial_small", "axial_large", "transformer", "transformer_dist"],
        help="Architecture preset (Track G)",
    )
    p.add_argument(
        "--sequences",
        default=None,
        help="Optional fixture sequences JSON (e.g. fixtures/sequences/synthetic_totals.json)",
    )
    p.add_argument("--data-root", default=None, help="Optional multi-poll sequence store root")
    args = p.parse_args()

    from hollersports.ml.axial_torch import torch_available, train_axial

    if not torch_available():
        print(
            json.dumps(
                {
                    "error": "torch_not_installed",
                    "hint": 'pip install -e "packages/hollersports[torch]"',
                }
            ),
            file=sys.stderr,
        )
        return 2
    try:
        result = train_axial(
            args.train_days,
            out_dir=args.out_dir,
            epochs=args.epochs,
            seed=args.seed,
            lr=args.lr,
            arch_preset=args.arch,
            data_root=args.data_root,
            fixture_sequence_path=args.sequences,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
