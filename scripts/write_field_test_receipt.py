#!/usr/bin/env python3
"""Write freeze field-test receipt from latest smoke / ml-e2e / backfill evidence."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "FIELD_TEST_RECEIPT_v0.5.0.json"


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _backfill_status() -> dict:
    try:
        text = subprocess.check_output(
            ["python3", "scripts/backfill_status.py"],
            cwd=ROOT,
            text=True,
            env={**dict(**__import__("os").environ), "PYTHONPATH": str(ROOT / "packages" / "hollersports")},
        )
    except (OSError, subprocess.CalledProcessError):
        return {}
    start = text.find("{")
    if start < 0:
        return {}
    # find matching JSON object (first top-level)
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        # truncated pretty print — try line-based
        depth = 0
        end = start
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return {}


def main() -> int:
    smoke = _load(ROOT / "docs" / "evidence" / "smoke_operator_day.last.json")
    ml = _load(ROOT / "docs" / "evidence" / "ml_pipeline_e2e.last.json")
    bf = _backfill_status()
    cal = bf.get("calibration") if isinstance(bf.get("calibration"), dict) else {}

    smoke_ok = bool(smoke) and (
        smoke.get("status") in {None, "OK", "COMPUTED"} or "core_hash" in smoke
    )
    ml_ok = (
        ml.get("status") == "ADVISORY_ONLY"
        and ml.get("capital_authority") is False
        and ml.get("execution_authority") is False
        and int((ml.get("candidates") or {}).get("count") or 0) >= 1
    )
    verdict = "FIELD_TEST_READY" if smoke_ok and ml_ok else "NEEDS_ATTENTION"

    receipt = {
        "schema_version": "HollerFieldTestReceipt.v1",
        "freeze_tag": "v0.5.0-advisory-beta",
        "package_version": "0.5.0",
        "tip_sha": _git_sha(),
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "smoke": {
            "ok": smoke_ok,
            "status": smoke.get("status") or ("OK" if smoke_ok else "MISSING"),
            "path": "docs/evidence/smoke_operator_day.last.json",
        },
        "ml_e2e": {
            "ok": ml_ok,
            "status": ml.get("status"),
            "candidate_count": (ml.get("candidates") or {}).get("count"),
            "train_n": (ml.get("train") or {}).get("train_n"),
            "temperature": ((ml.get("train") or {}).get("metrics") or {}).get(
                "temperature"
            ),
            "capital_authority": ml.get("capital_authority"),
            "execution_authority": ml.get("execution_authority"),
            "path": "docs/evidence/ml_pipeline_e2e.last.json",
        },
        "backfill": {
            "current_sample": bf.get("current_sample"),
            "calibration_status": cal.get("status"),
            "needs_backfill": bf.get("needs_backfill"),
            "model_edge_allowed": cal.get("model_edge_allowed"),
            "note": "Growing sample is field-test work, not a freeze blocker",
        },
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "verdict": verdict,
        "checklist_doc": "docs/TRACK_F_FREEZE_AND_FIELD_TEST.md",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if verdict == "FIELD_TEST_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
