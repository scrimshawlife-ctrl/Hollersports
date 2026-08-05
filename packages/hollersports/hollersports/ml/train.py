"""Baseline trainers: pure-Python L2 logistic (default) + optional sklearn HGB."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.ml.features import FEATURE_NAMES
from hollersports.schemas.hashing import packet_hash

MODEL_KIND_LOGISTIC = "logistic_l2"
MODEL_KIND_SKLEARN_HGB = "sklearn_hist_gbdt"


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def train_logistic_l2(
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    *,
    lr: float = 0.15,
    epochs: int = 400,
    l2: float = 0.05,
    seed: int = 42,
) -> dict[str, Any]:
    """Batch L2 logistic regression. Deterministic given seed and row order."""
    if not X or len(X) != len(y):
        raise ValueError("X/y must be non-empty and same length")
    n_features = len(X[0])
    if any(len(row) != n_features for row in X):
        raise ValueError("ragged feature rows")
    rng = random.Random(seed)
    # Tiny deterministic init (not zero so ties break stably).
    weights = [rng.uniform(-0.01, 0.01) for _ in range(n_features)]
    bias = 0.0
    n = float(len(X))

    for _ in range(epochs):
        grad_w = [0.0] * n_features
        grad_b = 0.0
        for row, label in zip(X, y):
            z = bias + sum(w * x for w, x in zip(weights, row))
            p = _sigmoid(z)
            err = p - float(label)
            for j in range(n_features):
                grad_w[j] += err * row[j]
            grad_b += err
        for j in range(n_features):
            weights[j] -= lr * ((grad_w[j] / n) + l2 * weights[j])
        bias -= lr * (grad_b / n)

    return {
        "kind": MODEL_KIND_LOGISTIC,
        "weights": weights,
        "bias": bias,
        "feature_names": list(FEATURE_NAMES),
        "hyperparams": {
            "lr": lr,
            "epochs": epochs,
            "l2": l2,
            "seed": seed,
        },
    }


def _try_sklearn_hgb(
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    *,
    seed: int = 42,
) -> dict[str, Any] | None:
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore
    except ImportError:
        return None
    clf = HistGradientBoostingClassifier(
        max_depth=3,
        max_iter=50,
        learning_rate=0.1,
        random_state=seed,
    )
    clf.fit([list(row) for row in X], list(y))
    # Serialize coefficients-free via joblib path later; store pickled base64 optional.
    # For portable CI, callers should prefer logistic. sklearn path stores model under
    # companion joblib file referenced by path in artifact.
    return {
        "kind": MODEL_KIND_SKLEARN_HGB,
        "feature_names": list(FEATURE_NAMES),
        "sklearn_estimator": clf,
        "hyperparams": {"max_depth": 3, "max_iter": 50, "seed": seed},
    }


def train_baseline(
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    *,
    prefer_sklearn: bool = False,
    seed: int = 42,
) -> dict[str, Any]:
    """Train baseline. Uses sklearn HGB only if prefer_sklearn and importable."""
    if prefer_sklearn:
        sk = _try_sklearn_hgb(X, y, seed=seed)
        if sk is not None:
            return sk
    return train_logistic_l2(X, y, seed=seed)


def predict_proba_logistic(model: Mapping[str, Any], x: Sequence[float]) -> float:
    weights = list(model["weights"])
    bias = float(model["bias"])
    if len(weights) != len(x):
        raise ValueError("feature length mismatch")
    z = bias + sum(w * float(v) for w, v in zip(weights, x))
    return _sigmoid(z)


def predict_proba(model: Mapping[str, Any], x: Sequence[float]) -> float:
    kind = str(model.get("kind") or "")
    if kind == MODEL_KIND_LOGISTIC:
        return predict_proba_logistic(model, x)
    if kind == MODEL_KIND_SKLEARN_HGB:
        clf = model.get("sklearn_estimator")
        if clf is None:
            raise ValueError("sklearn model missing estimator")
        proba = clf.predict_proba([list(x)])[0]
        # class 1 probability
        classes = list(getattr(clf, "classes_", [0, 1]))
        if 1 in classes:
            return float(proba[classes.index(1)])
        return float(proba[-1])
    raise ValueError(f"unknown model kind: {kind}")


def brier_score(
    model: Mapping[str, Any],
    X: Sequence[Sequence[float]],
    y: Sequence[int],
) -> float:
    if not X:
        return 0.0
    s = 0.0
    for row, label in zip(X, y):
        p = predict_proba(model, row)
        s += (p - float(label)) ** 2
    return s / len(X)


def model_to_serializable(model: Mapping[str, Any]) -> dict[str, Any]:
    """JSON-safe model (sklearn estimators excluded — use save_model)."""
    kind = str(model.get("kind") or "")
    if kind == MODEL_KIND_SKLEARN_HGB:
        raise ValueError("use save_model for sklearn artifacts")
    return {
        "kind": kind,
        "weights": [float(w) for w in model["weights"]],
        "bias": float(model["bias"]),
        "feature_names": list(model.get("feature_names") or FEATURE_NAMES),
        "hyperparams": dict(model.get("hyperparams") or {}),
        "metrics": dict(model.get("metrics") or {}),
        "provenance": dict(model.get("provenance") or {}),
        "model_id": str(model.get("model_id") or ""),
        "data_hash": str(model.get("data_hash") or ""),
    }


def save_model(model: Mapping[str, Any], path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    kind = str(model.get("kind") or "")
    if kind == MODEL_KIND_SKLEARN_HGB:
        try:
            import joblib  # type: ignore
        except ImportError as exc:
            raise ImportError("joblib/sklearn required to save HGB model") from exc
        joblib_path = out.with_suffix(".joblib")
        joblib.dump(model["sklearn_estimator"], joblib_path)
        meta = {
            "kind": kind,
            "feature_names": list(model.get("feature_names") or FEATURE_NAMES),
            "hyperparams": dict(model.get("hyperparams") or {}),
            "metrics": dict(model.get("metrics") or {}),
            "provenance": dict(model.get("provenance") or {}),
            "model_id": str(model.get("model_id") or ""),
            "data_hash": str(model.get("data_hash") or ""),
            "joblib_path": joblib_path.name,
        }
        out.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return out

    payload = model_to_serializable(model)
    payload["artifact_hash"] = packet_hash(payload)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def load_model(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    meta = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ValueError("invalid model file")
    kind = str(meta.get("kind") or "")
    if kind == MODEL_KIND_SKLEARN_HGB:
        try:
            import joblib  # type: ignore
        except ImportError as exc:
            raise ImportError("joblib/sklearn required to load HGB model") from exc
        joblib_name = str(meta.get("joblib_path") or p.with_suffix(".joblib").name)
        clf = joblib.load(p.parent / joblib_name)
        meta = dict(meta)
        meta["sklearn_estimator"] = clf
        return meta
    return meta
