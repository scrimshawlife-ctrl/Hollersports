#!/usr/bin/env python3
"""Report what fixture backfill is needed (Hermes / agent discovery entrypoint).

Prints JSON (and optional human lines) describing:
  - available fixtures
  - current cumulative settlement sample
  - whether needs_backfill
  - suggested command

Advisory only — no network, no money, no books.
Exit codes:
  0  ok (or --assert-min-sample met)
  1  assert failed (sample below target)
  2  usage / path error
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Repo root = parent of scripts/
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATA_ROOT = REPO_ROOT / "data" / "backfill"
DEFAULT_RECEIPT = REPO_ROOT / "docs" / "evidence" / "backfill_calibration.last.json"
DEFAULT_TARGET = 20  # matches DEFAULT_MIN_SAMPLE_RELIABLE
PLAYBOOK = "docs/agents/HERMES_BACKFILL.md"


def _discover_fixtures(fixtures_root: Path) -> list[dict]:
    found: list[dict] = []
    if not fixtures_root.is_dir():
        return found
    for child in sorted(fixtures_root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta = child / "meta.json"
        odds = child / "odds_records.json"
        results = child / "results.json"
        espn = child / "espn_events.json"
        complete = meta.is_file() and odds.is_file() and results.is_file()
        run_id = None
        note = None
        if meta.is_file():
            try:
                raw = json.loads(meta.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    run_id = raw.get("run_id")
                    note = raw.get("note")
            except (OSError, json.JSONDecodeError):
                pass
        found.append(
            {
                "id": child.name,
                "path": str(child.relative_to(REPO_ROOT))
                if child.is_relative_to(REPO_ROOT)
                else str(child),
                "complete": complete,
                "has_espn_events": espn.is_file(),
                "run_id": run_id,
                "note": note,
                "ready_for_backfill": complete,
            }
        )
    return found


def _sample_size(data_root: Path) -> int:
    hist = data_root / "ledgers" / "settlements_history.jsonl"
    if not hist.is_file():
        return 0
    n = 0
    settled = frozenset({"WIN", "LOSS", "PUSH", "VOID"})
    for line in hist.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and str(row.get("status") or "").upper() in settled:
            n += 1
    return n


def _load_receipt(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _calibration_snapshot(data_root: Path) -> dict:
    """Best-effort ladder status without hard-failing if package missing."""
    try:
        sys.path.insert(0, str(REPO_ROOT / "packages" / "hollersports"))
        from hollersports.paper.settlement_history import read_settlement_history
        from hollersports.runes.calibration_evaluator import evaluate_calibration

        rows = read_settlement_history(data_root=data_root, settled_only=True)
        cal = evaluate_calibration(rows, allow_forecast_weighting=True)
        return {
            "status": cal.get("status"),
            "reliability_status": cal.get("reliability_status"),
            "sample_size": cal.get("sample_size"),
            "hit_rate": cal.get("hit_rate"),
            "sim_roi": cal.get("sim_roi"),
            "model_edge_allowed": cal.get("model_edge_allowed"),
            "failed_gates": cal.get("failed_gates"),
        }
    except Exception as exc:  # noqa: BLE001 — status tool must stay resilient
        return {"status": "UNKNOWN", "error": str(exc), "sample_size": _sample_size(data_root)}


def build_report(
    *,
    fixtures_root: Path,
    data_root: Path,
    receipt_path: Path,
    target_sample: int,
    repeats: int,
    paper_top_n: int,
) -> dict:
    fixtures = _discover_fixtures(fixtures_root)
    ready_ids = [f["id"] for f in fixtures if f.get("ready_for_backfill")]
    incomplete = [f["id"] for f in fixtures if not f.get("ready_for_backfill")]
    current = _sample_size(data_root)
    receipt = _load_receipt(receipt_path)
    receipt_sample = None
    if receipt:
        receipt_sample = (receipt.get("calibration") or {}).get("sample_size")
        if receipt_sample is None:
            receipt_sample = receipt.get("cumulative_sample")

    needs = current < target_sample
    # Also need backfill if bank empty or no ready fixtures yet discovered
    if not ready_ids:
        needs = True  # cannot complete; still flag

    fixture_args = " ".join(ready_ids) if ready_ids else "day001 day002"
    suggested = (
        f"python scripts/backfill_fixtures.py "
        f"--fixtures {fixture_args} "
        f"--repeats {repeats} --paper-top-n {paper_top_n} "
        f"--data-root {data_root} "
        f"--out {receipt_path}"
    )

    cal = _calibration_snapshot(data_root)

    return {
        "schema_version": "HollerBackfillStatus.v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "playbook": PLAYBOOK,
        "repo_root": str(REPO_ROOT),
        "needs_backfill": bool(needs),
        "reason": (
            "no_complete_fixtures"
            if not ready_ids
            else (
                "sample_below_target"
                if current < target_sample
                else "sample_meets_target"
            )
        ),
        "fixtures_root": str(fixtures_root),
        "fixtures_available": ready_ids,
        "fixtures_incomplete": incomplete,
        "fixtures_detail": fixtures,
        "data_root": str(data_root),
        "settlements_history": str(
            data_root / "ledgers" / "settlements_history.jsonl"
        ),
        "current_sample": current,
        "target_sample": target_sample,
        "sample_gap": max(0, target_sample - current),
        "receipt_path": str(receipt_path),
        "receipt_exists": receipt_path.is_file(),
        "receipt_sample": receipt_sample,
        "calibration": cal,
        "suggested_command": suggested,
        "make_targets": {
            "status": "make backfill-status",
            "run": "make backfill",
        },
        "product_law": {
            "mode": "PAPER_ONLY",
            "capital_authority": False,
            "execution_authority": False,
            "real_money": False,
            "live_books": False,
        },
        "done_when": {
            "needs_backfill": False,
            "current_sample_gte": target_sample,
            "receipt_written": True,
            "note": "RELIABLE also needs hit_rate/sim_roi floors; sample floor is necessary not always sufficient",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=REPO_ROOT / "fixtures",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=DEFAULT_RECEIPT,
    )
    parser.add_argument(
        "--target-sample",
        type=int,
        default=DEFAULT_TARGET,
        help=f"Sample floor for needs_backfill (default {DEFAULT_TARGET})",
    )
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--paper-top-n", type=int, default=50)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON only (default is JSON + short human summary)",
    )
    parser.add_argument(
        "--assert-min-sample",
        type=int,
        default=None,
        metavar="N",
        help="Exit 1 if current_sample < N (Hermes gate)",
    )
    args = parser.parse_args()

    report = build_report(
        fixtures_root=args.fixtures_root,
        data_root=args.data_root,
        receipt_path=args.receipt,
        target_sample=args.target_sample,
        repeats=args.repeats,
        paper_top_n=args.paper_top_n,
    )

    print(json.dumps(report, indent=2, sort_keys=True))

    if not args.json:
        print(
            "\n# Hermes summary\n"
            f"playbook: {report['playbook']}\n"
            f"needs_backfill: {report['needs_backfill']} ({report['reason']})\n"
            f"sample: {report['current_sample']} / target {report['target_sample']} "
            f"(gap {report['sample_gap']})\n"
            f"fixtures: {', '.join(report['fixtures_available']) or 'NONE'}\n"
            f"calibration.status: {(report.get('calibration') or {}).get('status')}\n"
            f"run: {report['suggested_command']}\n",
            file=sys.stderr,
        )

    if args.assert_min_sample is not None:
        if report["current_sample"] < args.assert_min_sample:
            print(
                f"ASSERT_FAIL: sample {report['current_sample']} "
                f"< {args.assert_min_sample}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
