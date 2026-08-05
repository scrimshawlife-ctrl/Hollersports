#!/usr/bin/env python3
"""CLI: free-first closed operator day into the calibration bank (advisory only).

Examples (CI-safe injection):
  python scripts/free_first_operator_day.py \\
    --espn-raw path/to/espn.json --odds-raw path/to/odds.json \\
    --settle-espn-raw path/to/finals.json \\
    --leagues NBA --data-root data/backfill \\
    --out docs/evidence/free_first_day.last.json

Live (optional network; never places bets):
  python scripts/free_first_operator_day.py --leagues NBA --fetch-espn-finals \\
    --data-root data/backfill --out out/free_first_day.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hollersports.pipelines.free_first_day import run_free_first_operator_day


def _load_json(path: Path | None):
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", type=Path, default=Path("data/backfill"))
    p.add_argument(
        "--out",
        type=Path,
        default=Path("docs/evidence/free_first_day.last.json"),
    )
    p.add_argument("--run-id", default=None)
    p.add_argument("--leagues", default=None, help="Comma-separated day-one leagues")
    p.add_argument("--espn-raw", type=Path, default=None, help="Injected ESPN scoreboard")
    p.add_argument("--odds-raw", type=Path, default=None, help="Injected Odds API list JSON")
    p.add_argument(
        "--settle-espn-raw",
        type=Path,
        default=None,
        help="Injected ESPN finals scoreboard for settle (CI-safe)",
    )
    p.add_argument("--espn-only", action="store_true", help="Skip odds fetch")
    p.add_argument("--odds-only", action="store_true", help="Skip ESPN schedule fetch")
    p.add_argument(
        "--fetch-espn-finals",
        action="store_true",
        help="Opt-in live ESPN fetch for settle when no --settle-espn-raw",
    )
    p.add_argument("--paper-top-n", type=int, default=20)
    args = p.parse_args()

    leagues = None
    if args.leagues:
        leagues = [part.strip() for part in args.leagues.split(",") if part.strip()]

    espn_raw = _load_json(args.espn_raw)
    odds_raw = _load_json(args.odds_raw)
    if odds_raw is not None and not isinstance(odds_raw, list):
        print("odds-raw must be a JSON list", file=sys.stderr)
        return 2
    settle_raw = _load_json(args.settle_espn_raw)

    # Injected raw is consumed when fetch_* is True (pack skips network).
    # Only disable a source when the operator explicitly opts out.
    fetch_espn = not args.odds_only
    fetch_odds = not args.espn_only

    out = run_free_first_operator_day(
        data_root=args.data_root,
        run_id=args.run_id,
        leagues=leagues,
        espn_raw=espn_raw if isinstance(espn_raw, dict) else None,
        odds_raw=odds_raw,
        settle_espn_raw=settle_raw if isinstance(settle_raw, dict) else None,
        fetch_espn=fetch_espn,
        fetch_odds=fetch_odds,
        fetch_espn_finals=bool(args.fetch_espn_finals) and settle_raw is None,
        paper_top_n=args.paper_top_n,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    if out.get("capital_authority") or out.get("execution_authority"):
        return 2
    return 0 if out.get("status") != "NOT_COMPUTABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
