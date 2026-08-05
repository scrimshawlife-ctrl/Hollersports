#!/usr/bin/env python3
"""Build feature JSONL from fixture day directories (advisory / offline)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root without install
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.ml.features import (  # noqa: E402
    build_feature_rows,
    features_data_hash,
    write_features_jsonl,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "days",
        nargs="+",
        help="Fixture day directories (e.g. fixtures/day001 fixtures/day002)",
    )
    p.add_argument(
        "--out",
        default="data/ml/features.jsonl",
        help="Output JSONL path",
    )
    p.add_argument(
        "--require-labels",
        action="store_true",
        help="Drop markets without WIN/LOSS labels",
    )
    args = p.parse_args()
    rows = build_feature_rows(args.days, require_labels=args.require_labels)
    path = write_features_jsonl(rows, args.out)
    meta = {
        "n_rows": len(rows),
        "n_labeled": sum(1 for r in rows if "y" in r),
        "data_hash": features_data_hash(rows),
        "out": str(path),
        "capital_authority": False,
        "execution_authority": False,
    }
    print(json.dumps(meta, indent=2))
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
