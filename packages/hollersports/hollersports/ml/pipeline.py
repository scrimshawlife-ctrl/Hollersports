"""End-to-end offline ML pipeline helpers (fixtures → ensemble → annotate)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from hollersports.ml.calibrate import (
    build_ensemble_artifact,
    calibrate_temperature,
    save_ensemble,
)
from hollersports.ml.features import (
    build_feature_rows,
    features_data_hash,
    write_features_jsonl,
)
from hollersports.ml.train import brier_score, predict_proba, save_model, train_baseline


def run_train_calibrate(
    train_days: Sequence[Path | str],
    val_days: Sequence[Path | str] | None,
    *,
    out_dir: Path | str,
    prefer_sklearn: bool = False,
    seed: int = 42,
) -> dict[str, Any]:
    """Train on train_days, temperature-calibrate on val_days (or holdout split).

    Writes features.jsonl, model JSON, ensemble JSON under out_dir.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    train_rows = build_feature_rows(train_days, require_labels=True)
    if len(train_rows) < 2:
        raise ValueError(f"need >=2 labeled train rows, got {len(train_rows)}")

    if val_days:
        val_rows = build_feature_rows(val_days, require_labels=True)
        split_mode = "explicit_val_days"
    else:
        # Hold out only when the bank is large enough that calibration is meaningful.
        # Fixture banks (~10 labels) keep all rows for train and identity temperature.
        n = len(train_rows)
        if n >= 16:
            n_val = max(4, n // 4)
            val_rows = train_rows[-n_val:]
            train_rows = train_rows[:-n_val]
            split_mode = "holdout_tail"
        else:
            val_rows = list(train_rows)
            split_mode = "full_train_identity_cal"

    write_features_jsonl(train_rows + val_rows, out / "features.jsonl")
    data_hash = features_data_hash(train_rows + val_rows)

    X_train = [r["x"] for r in train_rows]
    y_train = [int(r["y"]) for r in train_rows]
    model = train_baseline(X_train, y_train, prefer_sklearn=prefer_sklearn, seed=seed)
    train_brier = brier_score(model, X_train, y_train)

    X_val = [r["x"] for r in val_rows] if val_rows else X_train
    y_val = [int(r["y"]) for r in val_rows] if val_rows else y_train
    raw_probs = [predict_proba(model, x) for x in X_val]
    # Never temperature-fit on the same rows used to train (overconfident T).
    if split_mode == "full_train_identity_cal":
        from hollersports.ml.calibrate import brier_calibrated, nll

        cal = {
            "temperature": 1.0,
            "val_nll": nll(raw_probs, y_val, temperature=1.0),
            "val_brier": brier_calibrated(raw_probs, y_val, temperature=1.0),
            "val_brier_raw": brier_calibrated(raw_probs, y_val, temperature=1.0),
            "n_val": len(y_val),
            "temperature_source": "identity_train_eq_val",
            "min_val_for_temperature": 8,
        }
    else:
        cal = calibrate_temperature(raw_probs, y_val)

    model_id = f"gbm_v{data_hash[:10]}"
    model = dict(model)
    model["model_id"] = model_id
    model["data_hash"] = data_hash
    model["metrics"] = {
        "train_brier": train_brier,
        "train_n": len(train_rows),
        "val_n": len(val_rows),
        "split_mode": split_mode,
        **{
            k: cal[k]
            for k in (
                "temperature",
                "val_nll",
                "val_brier",
                "val_brier_raw",
                "temperature_source",
            )
            if k in cal
        },
    }
    model["provenance"] = {
        "train_days": [str(d) for d in train_days],
        "val_days": [str(d) for d in (val_days or [])],
        "split_mode": split_mode,
        "status": "ADVISORY_ONLY",
        "capital_authority": False,
        "execution_authority": False,
    }

    model_path = out / f"{model_id}.json"
    # sklearn path needs special save; logistic is JSON
    if str(model.get("kind")) == "sklearn_hist_gbdt":
        save_model(model, model_path)
    else:
        save_model(model, model_path)

    ensemble = build_ensemble_artifact(
        base_model_path=model_path.name,
        base_model_id=model_id,
        temperature=float(cal["temperature"]),
        metrics=dict(model["metrics"]),
        data_hash=data_hash,
    )
    ensemble_path = out / "ensemble.json"
    save_ensemble(ensemble, ensemble_path)

    # Provenance model card (markdown + JSON) next to artifacts
    card_paths: dict[str, str] = {}
    try:
        from hollersports.ml.model_card import write_model_card

        card = write_model_card(ensemble_path, out_dir=out / "model_cards")
        card_paths = {
            "model_card_md": str(card.get("written_md") or ""),
            "model_card_json": str(card.get("written_json") or ""),
        }
    except (OSError, ValueError, FileNotFoundError):
        card_paths = {}

    return {
        "model_path": str(model_path),
        "ensemble_path": str(ensemble_path),
        "features_path": str(out / "features.jsonl"),
        "model_id": model_id,
        "ensemble_id": ensemble["ensemble_id"],
        "metrics": model["metrics"],
        "train_n": len(train_rows),
        "val_n": len(val_rows),
        "data_hash": data_hash,
        **card_paths,
        "capital_authority": False,
        "execution_authority": False,
    }
