"""Temperature scaling + ensemble sidecar (advisory calibration only)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.ml.train import predict_proba
from hollersports.schemas.hashing import packet_hash


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _logit(p: float, eps: float = 1e-6) -> float:
    p = min(1.0 - eps, max(eps, p))
    return math.log(p / (1.0 - p))


def apply_temperature(p: float, temperature: float) -> float:
    t = max(1e-3, float(temperature))
    return _sigmoid(_logit(p) / t)


def nll(
    probs: Sequence[float],
    y: Sequence[int],
    *,
    temperature: float = 1.0,
) -> float:
    if not probs:
        return 0.0
    total = 0.0
    for p, label in zip(probs, y):
        pc = apply_temperature(p, temperature)
        pc = min(1.0 - 1e-9, max(1e-9, pc))
        if label:
            total -= math.log(pc)
        else:
            total -= math.log(1.0 - pc)
    return total / len(probs)


def brier_calibrated(
    probs: Sequence[float],
    y: Sequence[int],
    *,
    temperature: float = 1.0,
) -> float:
    if not probs:
        return 0.0
    s = 0.0
    for p, label in zip(probs, y):
        pc = apply_temperature(p, temperature)
        s += (pc - float(label)) ** 2
    return s / len(probs)


# Below this validation size, temperature grid-search is noise-dominated and
# often collapses useful edges (e.g. T=4 on n=2). Stay at T=1.0 until sample grows.
DEFAULT_MIN_VAL_FOR_TEMPERATURE = 8


def calibrate_temperature(
    probs: Sequence[float],
    y: Sequence[int],
    *,
    grid: Sequence[float] | None = None,
    min_val_for_temperature: int = DEFAULT_MIN_VAL_FOR_TEMPERATURE,
    max_temperature: float = 2.5,
) -> dict[str, Any]:
    """Grid-search temperature minimizing NLL on validation probs.

    Small-n guard: if ``len(y) < min_val_for_temperature``, force T=1.0 so
    calibration does not erase model edge on fixture-sized banks.
    ``max_temperature`` caps over-shrink even when n is adequate.
    """
    if not probs or len(probs) != len(y):
        raise ValueError("probs/y must be non-empty and same length")
    n_val = len(y)
    raw_brier = brier_calibrated(probs, y, temperature=1.0)
    raw_nll = nll(probs, y, temperature=1.0)

    if n_val < int(min_val_for_temperature):
        return {
            "temperature": 1.0,
            "val_nll": raw_nll,
            "val_brier": raw_brier,
            "val_brier_raw": raw_brier,
            "n_val": n_val,
            "temperature_source": "identity_small_val",
            "min_val_for_temperature": int(min_val_for_temperature),
        }

    # Prefer mild temperatures; extreme T on tiny sports samples kills EV signal.
    candidates = list(grid) if grid is not None else [
        0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5
    ]
    t_cap = max(1e-3, float(max_temperature))
    candidates = [t for t in candidates if t <= t_cap + 1e-12]
    if 1.0 not in candidates:
        candidates.append(1.0)

    best_t = 1.0
    best_nll = float("inf")
    for t in candidates:
        score = nll(probs, y, temperature=t)
        if score < best_nll - 1e-15 or (
            abs(score - best_nll) <= 1e-15 and t < best_t
        ):
            best_nll = score
            best_t = float(t)
    return {
        "temperature": best_t,
        "val_nll": best_nll,
        "val_brier": brier_calibrated(probs, y, temperature=best_t),
        "val_brier_raw": raw_brier,
        "n_val": n_val,
        "temperature_source": "grid_nll",
        "min_val_for_temperature": int(min_val_for_temperature),
        "max_temperature": t_cap,
    }


def build_ensemble_artifact(
    *,
    base_model_path: str,
    base_model_id: str,
    temperature: float,
    metrics: Mapping[str, Any],
    data_hash: str,
    blend_weight: float = 1.0,
) -> dict[str, Any]:
    """Single-model ensemble with temperature (multi-model blend later)."""
    art = {
        "schema_version": "HollerEnsemble.v1",
        "models": [
            {
                "model_id": base_model_id,
                "path": base_model_path,
                "weight": float(blend_weight),
            }
        ],
        "temperature": float(temperature),
        "metrics": dict(metrics),
        "data_hash": data_hash,
        "capital_authority": False,
        "execution_authority": False,
        "authority": "SHADOW_ONLY",
    }
    art["artifact_hash"] = packet_hash(art)
    art["ensemble_id"] = f"ensemble_{art['artifact_hash'][:12]}"
    return art


def save_ensemble(art: Mapping[str, Any], path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(art), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def load_ensemble(path: Path | str) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("invalid ensemble file")
    return raw


def predict_calibrated(
    model: Mapping[str, Any],
    x: Sequence[float],
    *,
    temperature: float = 1.0,
) -> float:
    raw = predict_proba(model, x)
    return apply_temperature(raw, temperature)
