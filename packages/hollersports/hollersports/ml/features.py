"""Feature engineering from fixture markets (no invented odds).

Pure stdlib. Odds-delta from history/cross-book when present; sentiment from
explicit score or offline lexicon on optional text fields (else 0.0).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.ml.sentiment import resolve_market_sentiment
from hollersports.schemas.hashing import packet_hash

# Stable feature order for train / apply. Do not reorder without bumping model version.
FEATURE_NAMES: tuple[str, ...] = (
    "implied_probability",
    "consensus_score",
    "public_bet_pct",
    "handle_pct",
    "clv_retention",
    "is_home",
    "price_norm",
    "odds_delta",
    "sentiment_score",
)

_SETTLED_POS = frozenset({"WIN"})
_SETTLED_NEG = frozenset({"LOSS"})
_SKIP_LABELS = frozenset({"PUSH", "VOID", "PENDING", ""})


def american_to_implied(price: float | int | None) -> float | None:
    """Convert American odds to rough implied probability (no vig strip)."""
    if price is None:
        return None
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p == 0:
        return None
    if p > 0:
        return 100.0 / (p + 100.0)
    return abs(p) / (abs(p) + 100.0)


def american_to_decimal(price: float | int | None) -> float | None:
    """American → decimal odds for EV."""
    if price is None:
        return None
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p == 0:
        return None
    if p > 0:
        return 1.0 + (p / 100.0)
    return 1.0 + (100.0 / abs(p))


def _f(raw: Any, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _odds_delta(market: Mapping[str, Any]) -> float:
    """Δ implied over history if present; else 0 (fail soft, never invent)."""
    hist = market.get("odds_history") or market.get("price_history")
    if not isinstance(hist, list) or len(hist) < 2:
        # Optional explicit fields
        if market.get("odds_delta") is not None:
            return _f(market.get("odds_delta"), 0.0)
        return 0.0
    imps: list[float] = []
    for point in hist:
        if isinstance(point, Mapping):
            imp = point.get("implied_probability")
            if imp is None:
                imp = american_to_implied(point.get("price"))
            if imp is not None:
                imps.append(float(imp))
        elif isinstance(point, (int, float)):
            imp = american_to_implied(point)
            if imp is not None:
                imps.append(imp)
    if len(imps) < 2:
        return 0.0
    return imps[-1] - imps[0]


def extract_feature_vector(market: Mapping[str, Any]) -> dict[str, float] | None:
    """Build named feature map from a market row. None if price/implied unusable."""
    price = market.get("price")
    implied = market.get("market_implied_probability")
    if implied is None:
        implied = market.get("implied_probability")
    if implied is None:
        implied = american_to_implied(price)
    try:
        implied_f = float(implied) if implied is not None else None
    except (TypeError, ValueError):
        return None
    if implied_f is None or not (0.0 < implied_f < 1.0):
        return None

    selection = str(market.get("selection") or "").upper()
    is_home = 1.0 if "HOME" in selection else 0.0
    try:
        price_f = float(price) if price is not None else 0.0
    except (TypeError, ValueError):
        price_f = 0.0
    # Bound American prices roughly into [-1, 1] for stable logistics.
    price_norm = max(-1.0, min(1.0, price_f / 200.0))

    # Sentiment: explicit score or lexicon on headline/snippet; never invent text.
    # Map [-1, 1] → roughly centered feature (keep signed value for model).
    sent = resolve_market_sentiment(market)

    return {
        "implied_probability": implied_f,
        "consensus_score": _f(market.get("consensus_score"), 0.5),
        "public_bet_pct": _f(market.get("public_bet_pct"), 0.5),
        "handle_pct": _f(market.get("handle_pct"), 0.5),
        "clv_retention": _f(market.get("clv_retention"), 0.0),
        "is_home": is_home,
        "price_norm": price_norm,
        "odds_delta": _odds_delta(market),
        "sentiment_score": float(sent),
    }


def vector_list(feat: Mapping[str, float]) -> list[float]:
    return [float(feat[name]) for name in FEATURE_NAMES]


def _load_markets(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [m for m in raw if isinstance(m, dict)]
    if isinstance(raw, dict):
        markets = raw.get("markets")
        if isinstance(markets, list):
            return [m for m in markets if isinstance(m, dict)]
    return []


def _load_results(path: Path) -> dict[str, str]:
    """market_id → result label (WIN/LOSS/…)."""
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows: list[Any]
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        rows = list(raw.get("results") or [])
    else:
        return {}
    out: dict[str, str] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        mid = str(r.get("market_id") or "")
        if not mid:
            continue
        out[mid] = str(r.get("result") or "").upper()
    return out


def build_feature_rows(
    fixture_days: Sequence[Path | str],
    *,
    require_labels: bool = False,
) -> list[dict[str, Any]]:
    """Load markets (+ optional results) from fixture day dirs into feature rows.

    Each row includes: market_id, event_id, selection, price, features, x, y (if labeled).
    """
    rows: list[dict[str, Any]] = []
    for day in fixture_days:
        day_path = Path(day)
        odds_path = day_path / "odds_records.json"
        if not odds_path.is_file():
            continue
        markets = _load_markets(odds_path)
        labels = _load_results(day_path / "results.json")
        day_id = day_path.name
        for market in markets:
            feat = extract_feature_vector(market)
            if feat is None:
                continue
            mid = str(market.get("market_id") or "")
            label_raw = labels.get(mid, "")
            y: int | None = None
            if label_raw in _SETTLED_POS:
                y = 1
            elif label_raw in _SETTLED_NEG:
                y = 0
            elif require_labels:
                continue
            elif label_raw in _SKIP_LABELS or not label_raw:
                y = None
            else:
                y = None

            if require_labels and y is None:
                continue

            row: dict[str, Any] = {
                "day_id": day_id,
                "market_id": mid,
                "event_id": str(market.get("event_id") or ""),
                "selection": str(market.get("selection") or ""),
                "price": market.get("price"),
                "features": feat,
                "x": vector_list(feat),
            }
            if y is not None:
                row["y"] = y
                row["label"] = label_raw
            rows.append(row)
    return rows


def features_data_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    """Stable hash of feature matrix + ids for provenance."""
    payload = [
        {
            "market_id": r.get("market_id"),
            "x": r.get("x"),
            "y": r.get("y"),
        }
        for r in rows
    ]
    return packet_hash({"rows": payload, "feature_names": list(FEATURE_NAMES)})


def write_features_jsonl(rows: Sequence[Mapping[str, Any]], path: Path | str) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    return out


def read_features_jsonl(path: Path | str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
    return out
