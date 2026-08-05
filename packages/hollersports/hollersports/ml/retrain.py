"""Hermes-oriented retrain evaluator (advisory proposals only).

Computes Brier / edge diagnostics on labeled feature rows vs a loaded model
and emits an UPDATE-style proposal when quality degrades. Never trains
automatically; never grants capital/execution authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.ml.calibrate import apply_temperature, load_ensemble
from hollersports.ml.features import build_feature_rows
from hollersports.ml.train import load_model, predict_proba
from hollersports.schemas.hashing import packet_hash

# Default: retrain when validation Brier is worse than baseline by this much.
DEFAULT_BRIER_DEGRADE = 0.01
DEFAULT_MIN_LABELED = 8


def evaluate_model_on_rows(
    model: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    temperature: float = 1.0,
) -> dict[str, Any]:
    """Brier + simple edge metrics on labeled rows. Empty → NOT_COMPUTABLE."""
    labeled = [r for r in rows if "y" in r and "x" in r]
    if not labeled:
        return {
            "status": "NOT_COMPUTABLE",
            "reason": "no_labeled_rows",
            "sample_size": 0,
            "brier": None,
            "hit_rate_at_half": None,
        }
    brier_sum = 0.0
    hits = 0
    for r in labeled:
        p = apply_temperature(predict_proba(model, r["x"]), temperature)
        y = int(r["y"])
        brier_sum += (p - y) ** 2
        if (p >= 0.5 and y == 1) or (p < 0.5 and y == 0):
            hits += 1
    n = len(labeled)
    return {
        "status": "COMPUTED",
        "sample_size": n,
        "brier": round(brier_sum / n, 6),
        "hit_rate_at_half": round(hits / n, 4),
        "temperature": float(temperature),
    }


def propose_retrain(
    *,
    ensemble_path: Path | str,
    eval_fixture_days: Sequence[Path | str],
    baseline_brier: float | None = None,
    brier_degrade: float = DEFAULT_BRIER_DEGRADE,
    min_labeled: int = DEFAULT_MIN_LABELED,
) -> dict[str, Any]:
    """Build an advisory retrain proposal packet.

    Status:
      * HOLD — sample too small or metrics within tolerance
      * RETRAIN_SUGGESTED — Brier degraded vs baseline by threshold
      * NOT_COMPUTABLE — missing model/ensemble or no labels
    """
    ep = Path(ensemble_path)
    if not ep.is_file():
        return {
            "schema_version": "HollerMlRetrainProposal.v1",
            "status": "NOT_COMPUTABLE",
            "reason": "ensemble_missing",
            "capital_authority": False,
            "execution_authority": False,
            "authority": "SHADOW_ONLY",
            "mode": "ADVISORY_ONLY",
        }
    try:
        art = load_ensemble(ep)
        models = art.get("models") or []
        rel = str((models[0] or {}).get("path") or "")
        mp = Path(rel) if Path(rel).is_file() else ep.parent / Path(rel).name
        model = load_model(mp)
    except (OSError, ValueError, KeyError, FileNotFoundError) as exc:
        return {
            "schema_version": "HollerMlRetrainProposal.v1",
            "status": "NOT_COMPUTABLE",
            "reason": f"load_failed:{exc}",
            "capital_authority": False,
            "execution_authority": False,
            "authority": "SHADOW_ONLY",
            "mode": "ADVISORY_ONLY",
        }

    temperature = float(art.get("temperature") or 1.0)
    rows = build_feature_rows(eval_fixture_days, require_labels=True)
    metrics = evaluate_model_on_rows(model, rows, temperature=temperature)

    # Baseline: ensemble stored val_brier, or provided override
    stored = (art.get("metrics") or {}).get("val_brier")
    if baseline_brier is None and stored is not None:
        try:
            baseline_brier = float(stored)
        except (TypeError, ValueError):
            baseline_brier = None

    suggestion = "HOLD"
    reason = "within_tolerance"
    if metrics.get("status") != "COMPUTED":
        suggestion = "NOT_COMPUTABLE"
        reason = str(metrics.get("reason") or "no_metrics")
    elif int(metrics.get("sample_size") or 0) < int(min_labeled):
        suggestion = "HOLD"
        reason = "sample_below_min_labeled"
    elif baseline_brier is not None and metrics.get("brier") is not None:
        degrade = float(metrics["brier"]) - float(baseline_brier)
        if degrade >= float(brier_degrade):
            suggestion = "RETRAIN_SUGGESTED"
            reason = f"brier_degraded_by_{round(degrade, 4)}"
        else:
            reason = f"brier_delta_{round(degrade, 4)}"
    else:
        reason = "no_baseline_brier_hold"

    proposal = {
        "schema_version": "HollerMlRetrainProposal.v1",
        "status": suggestion,
        "reason": reason,
        "ensemble_path": str(ep),
        "ensemble_id": art.get("ensemble_id"),
        "model_id": (models[0] or {}).get("model_id") if models else None,
        "baseline_brier": baseline_brier,
        "brier_degrade_threshold": float(brier_degrade),
        "min_labeled": int(min_labeled),
        "eval_metrics": metrics,
        "eval_days": [str(d) for d in eval_fixture_days],
        "suggested_command": (
            "python scripts/holler/train_gbm.py "
            + " ".join(str(d) for d in eval_fixture_days)
            + " --out-dir data/ml"
            if suggestion == "RETRAIN_SUGGESTED"
            else None
        ),
        "auto_retrain": False,
        "note": "advisory_proposal_only_human_or_hermes_must_approve",
        "capital_authority": False,
        "execution_authority": False,
        "authority": "SHADOW_ONLY",
        "mode": "ADVISORY_ONLY",
    }
    proposal["packet_hash"] = packet_hash(
        {k: v for k, v in proposal.items() if k != "packet_hash"}
    )
    return proposal


def write_proposal(proposal: Mapping[str, Any], path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(proposal), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
