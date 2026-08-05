#!/usr/bin/env python3
"""Write Obsidian-ready model card from ensemble.json (advisory provenance)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "packages" / "hollersports"))

from hollersports.ml.model_card import write_model_card  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--ensemble",
        default=str(_REPO / "data" / "ml" / "ensemble.json"),
    )
    p.add_argument(
        "--out-dir",
        default=None,
        help="Default: <ensemble_dir>/model_cards",
    )
    args = p.parse_args()
    try:
        card = write_model_card(args.ensemble, out_dir=args.out_dir)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc), "status": "FAIL_CLOSED"}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "model_id": card.get("model_id"),
                "written_md": card.get("written_md"),
                "written_json": card.get("written_json"),
                "packet_hash": card.get("packet_hash"),
                "capital_authority": False,
                "execution_authority": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
