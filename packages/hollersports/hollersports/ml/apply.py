"""Apply ensemble to markets — attach model_probability + EV (fail closed)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.ml.calibrate import load_ensemble, predict_calibrated
from hollersports.ml.ev import annotate_ev
from hollersports.ml.features import extract_feature_vector, vector_list
from hollersports.ml.train import load_model, predict_proba
from hollersports.schemas.hashing import packet_hash


def _resolve_model_path(ensemble_path: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_file():
        return candidate
    sibling = ensemble_path.parent / relative
    if sibling.is_file():
        return sibling
    # basename only
    return ensemble_path.parent / Path(relative).name


def load_ensemble_bundle(ensemble_path: Path | str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (ensemble_art, base_model). Fail closed if missing."""
    ep = Path(ensemble_path)
    if not ep.is_file():
        raise FileNotFoundError(f"ensemble not found: {ep}")
    art = load_ensemble(ep)
    models = art.get("models") or []
    if not models:
        raise ValueError("ensemble has no models")
    first = models[0]
    rel = str(first.get("path") or "")
    mp = _resolve_model_path(ep, rel)
    if not mp.is_file():
        raise FileNotFoundError(f"base model not found: {mp}")
    model = load_model(mp)
    return art, model


def score_market(
    market: Mapping[str, Any],
    *,
    model: Mapping[str, Any],
    temperature: float,
    ensemble_id: str,
    model_id: str,
    data_hash: str,
    artifact_hash: str,
    ev_threshold: float = 0.03,
) -> dict[str, Any] | None:
    """Return annotated market copy or None if features unavailable (skip, no invent)."""
    feat = extract_feature_vector(market)
    if feat is None:
        return None
    x = vector_list(feat)
    p_raw = predict_proba(model, x)
    p = predict_calibrated(model, x, temperature=temperature)
    # Clamp open interval for strategy validators
    p_raw = min(0.999, max(0.001, float(p_raw)))
    p = min(0.999, max(0.001, float(p)))
    implied = feat["implied_probability"]
    ev_block = annotate_ev(
        model_probability=p,
        american_price=market.get("price"),
        market_implied=implied,
        ev_threshold=ev_threshold,
    )
    out = dict(market)
    out["model_probability"] = p
    out["model_probability_raw"] = p_raw
    out["model_side"] = str(market.get("selection") or "UNKNOWN")
    out["market_implied_probability"] = implied
    out["model_edge"] = p - implied
    out["model_edge_raw"] = p_raw - implied
    out["expected_value"] = ev_block.get("expected_value")
    out["ev_meets_threshold"] = ev_block.get("ev_meets_threshold")
    out["ml_features"] = feat
    out["ml_provenance"] = {
        "ensemble_id": ensemble_id,
        "model_id": model_id,
        "data_hash": data_hash,
        "artifact_hash": artifact_hash,
        "temperature": temperature,
        "scoring": "logistic_or_sklearn_plus_temperature",
        "status": "ADVISORY_ONLY",
        "capital_authority": False,
        "execution_authority": False,
    }
    return out


def apply_ensemble_to_markets(
    markets: Sequence[Mapping[str, Any]],
    ensemble_path: Path | str,
    *,
    ev_threshold: float = 0.03,
    only_ev_positive: bool = False,
) -> list[dict[str, Any]]:
    art, model = load_ensemble_bundle(ensemble_path)
    temperature = float(art.get("temperature") or 1.0)
    ensemble_id = str(art.get("ensemble_id") or "")
    artifact_hash = str(art.get("artifact_hash") or "")
    data_hash = str(art.get("data_hash") or "")
    models = art.get("models") or []
    model_id = str((models[0] or {}).get("model_id") or model.get("model_id") or "")

    out: list[dict[str, Any]] = []
    for market in markets:
        if not isinstance(market, Mapping):
            continue
        scored = score_market(
            market,
            model=model,
            temperature=temperature,
            ensemble_id=ensemble_id,
            model_id=model_id,
            data_hash=data_hash,
            artifact_hash=artifact_hash,
            ev_threshold=ev_threshold,
        )
        if scored is None:
            continue
        if only_ev_positive and not scored.get("ev_meets_threshold"):
            continue
        out.append(scored)
    return out


def apply_ensemble_to_odds_file(
    odds_path: Path | str,
    ensemble_path: Path | str,
    *,
    out_path: Path | str | None = None,
    ev_threshold: float = 0.03,
) -> dict[str, Any]:
    """Annotate an odds_records.json file; write optional output."""
    op = Path(odds_path)
    raw = json.loads(op.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        markets = [m for m in (raw.get("markets") or []) if isinstance(m, dict)]
        wrapper = True
    elif isinstance(raw, list):
        markets = [m for m in raw if isinstance(m, dict)]
        wrapper = False
    else:
        raise ValueError("unrecognized odds file shape")

    scored = apply_ensemble_to_markets(markets, ensemble_path, ev_threshold=ev_threshold)
    payload: dict[str, Any] = {
        "schema_version": "HollerMlAnnotatedMarkets.v1",
        "source_odds": str(op),
        "ensemble_path": str(ensemble_path),
        "market_count": len(scored),
        "markets": scored,
        "capital_authority": False,
        "execution_authority": False,
        "authority": "SHADOW_ONLY",
    }
    payload["packet_hash"] = packet_hash(
        {
            "markets": [
                {
                    "market_id": m.get("market_id"),
                    "model_probability": m.get("model_probability"),
                    "expected_value": m.get("expected_value"),
                }
                for m in scored
            ]
        }
    )
    if out_path is not None:
        outp = Path(out_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        # Preserve wrapper shape for fixture-like re-ingest when useful
        if wrapper:
            body = {"markets": scored, "ml_meta": {
                "packet_hash": payload["packet_hash"],
                "ensemble_path": str(ensemble_path),
            }}
            outp.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            outp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["written_to"] = str(outp)
    return payload
