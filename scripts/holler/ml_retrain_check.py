#!/usr/bin/env python3
"""Advisory retrain check: evaluate ensemble on fixture days; never auto-trains."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.ml.retrain import propose_retrain, write_proposal  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--ensemble",
        default=str(_REPO / "data" / "ml" / "ensemble.json"),
        help="Path to ensemble.json",
    )
    p.add_argument(
        "eval_days",
        nargs="*",
        default=[
            str(_REPO / "fixtures" / "day001"),
            str(_REPO / "fixtures" / "day002"),
            str(_REPO / "fixtures" / "day003"),
        ],
        help="Labeled fixture days for evaluation",
    )
    p.add_argument(
        "--out",
        default=str(_REPO / "docs" / "evidence" / "ml_retrain_proposal.last.json"),
    )
    p.add_argument("--brier-degrade", type=float, default=0.01)
    p.add_argument("--min-labeled", type=int, default=8)
    args = p.parse_args()

    proposal = propose_retrain(
        ensemble_path=args.ensemble,
        eval_fixture_days=args.eval_days,
        brier_degrade=args.brier_degrade,
        min_labeled=args.min_labeled,
    )
    path = write_proposal(proposal, args.out)
    print(json.dumps({**proposal, "written_to": str(path)}, indent=2))
    # Exit 0 always for advisory; Hermes inspects status field
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
