#!/usr/bin/env python3
"""CLI: free-first live observation pack (advisory only; no money).

Examples:
  # Offline / CI-safe (no network): not useful alone — use fixtures.
  # Live ESPN schedule (no key):
  python scripts/holler_free_first_ingest.py --espn-only --out out/free_first.json

  # ESPN + Odds API when THE_ODDS_API_KEY is set:
  export THE_ODDS_API_KEY=...
  python scripts/holler_free_first_ingest.py --out out/free_first.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hollersports.sources.free_first_ingest import build_live_observation_pack


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("out/free_first_observation.json"))
    p.add_argument("--espn-only", action="store_true", help="Skip odds fetch")
    p.add_argument("--odds-only", action="store_true", help="Skip ESPN fetch")
    p.add_argument("--run-id", default=None)
    args = p.parse_args()

    pack = build_live_observation_pack(
        run_id=args.run_id,
        fetch_espn=not args.odds_only,
        fetch_odds=not args.espn_only,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": pack.get("status"),
                "espn_event_count": pack.get("espn_event_count"),
                "odds_event_count": pack.get("odds_event_count"),
                "conflict_status": (pack.get("conflict") or {}).get("status"),
                "errors": pack.get("errors"),
                "out": str(args.out),
                "capital_authority": False,
                "mode": "ADVISORY_ONLY",
            },
            indent=2,
        )
    )
    return 0 if pack.get("status") != "NOT_COMPUTABLE" or pack.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
