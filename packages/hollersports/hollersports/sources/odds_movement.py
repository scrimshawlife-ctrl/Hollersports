"""Odds movement / cross-book enrichment (advisory observation only).

Never invents prices. Fail soft: missing history → odds_delta 0.0.

Two signals (arxiv 2505.21275-style odds as leading indicators, offline-safe):

1. **Cross-book history** — when multi-book markets share event+type+selection,
   attach ``odds_history`` and a stable cross-book ``odds_delta``.
2. **Temporal snapshot** — optional prior implied from ``data_root`` snapshots
   on re-observe; true Δp between free-first polls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def price_to_implied(price: Any) -> float | None:
    """Implied probability from American or decimal odds. None if unusable.

    Conventions (match odds_api normalize):
      * American: <= -100 or >= 100
      * Decimal: (1, 100) exclusive of pure American range
      * Already a probability: (0, 1)
    """
    if price is None:
        return None
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p == 0:
        return None
    if 0.0 < p < 1.0:
        return p
    if p <= -100:
        return abs(p) / (abs(p) + 100.0)
    if p >= 100:
        return 100.0 / (p + 100.0)
    if p > 1.0:
        imp = 1.0 / p
        return imp if 0.0 < imp < 1.0 else None
    return None


def _stable_line_key(market: Mapping[str, Any]) -> str:
    eid = str(market.get("event_id") or "")
    mtype = str(market.get("market_type") or "")
    sel = str(market.get("selection") or "")
    point = market.get("point")
    return f"{eid}|{mtype}|{sel}|{point}"


def _group_key(market: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(market.get("event_id") or ""),
        str(market.get("market_type") or ""),
        str(market.get("selection") or ""),
        str(market.get("point") if market.get("point") is not None else ""),
    )


def enrich_markets_cross_book(
    markets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Attach odds_history / odds_delta / book_dispersion from multi-book peers.

    Does not invent prices. Single-book lines get empty history and odds_delta 0
    unless already set.
    """
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for m in markets:
        if not isinstance(m, Mapping):
            continue
        groups.setdefault(_group_key(m), []).append(dict(m))

    out: list[dict[str, Any]] = []
    for _key, peers in groups.items():
        # Stable order by sportsbook then market_id
        peers_sorted = sorted(
            peers,
            key=lambda r: (
                str(r.get("sportsbook") or ""),
                str(r.get("market_id") or ""),
            ),
        )
        history: list[dict[str, Any]] = []
        imps: list[float] = []
        for p in peers_sorted:
            imp = p.get("market_implied_probability")
            if imp is None:
                imp = p.get("implied_probability")
            if imp is None:
                imp = price_to_implied(p.get("price"))
            try:
                imp_f = float(imp) if imp is not None else None
            except (TypeError, ValueError):
                imp_f = None
            if imp_f is None or not (0.0 < imp_f < 1.0):
                continue
            imps.append(imp_f)
            history.append(
                {
                    "price": p.get("price"),
                    "implied_probability": imp_f,
                    "sportsbook": p.get("sportsbook"),
                    "market_id": p.get("market_id"),
                }
            )

        dispersion = (max(imps) - min(imps)) if len(imps) >= 2 else 0.0
        # Cross-book pseudo-movement: last − first in stable sportsbook order
        cross_delta = (imps[-1] - imps[0]) if len(imps) >= 2 else 0.0

        for p in peers_sorted:
            row = dict(p)
            if history:
                row.setdefault("odds_history", history)
            if row.get("odds_delta") is None:
                row["odds_delta"] = round(cross_delta, 6)
            row.setdefault("book_dispersion", round(dispersion, 6))
            row.setdefault(
                "market_implied_probability",
                price_to_implied(row.get("price"))
                if row.get("market_implied_probability") is None
                else row.get("market_implied_probability"),
            )
            out.append(row)
    return out


def snapshot_path(data_root: Path | str) -> Path:
    return Path(data_root) / "ml" / "odds_implied_snapshots.json"


def load_implied_snapshots(data_root: Path | str) -> dict[str, float]:
    path = snapshot_path(data_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if 0.0 < fv < 1.0:
            out[str(k)] = fv
    return out


def save_implied_snapshots(data_root: Path | str, snaps: Mapping[str, float]) -> Path:
    path = snapshot_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep only valid implieds
    clean = {
        str(k): float(v)
        for k, v in snaps.items()
        if isinstance(v, (int, float)) and 0.0 < float(v) < 1.0
    }
    path.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def apply_temporal_delta(
    markets: Sequence[Mapping[str, Any]],
    prior: Mapping[str, float],
) -> list[dict[str, Any]]:
    """Overlay temporal odds_delta when a prior implied exists for the line key.

    Prefer temporal Δ over cross-book when prior is present. Extends odds_history
    with a prior point when possible.
    """
    out: list[dict[str, Any]] = []
    for m in markets:
        if not isinstance(m, Mapping):
            continue
        row = dict(m)
        key = _stable_line_key(row)
        cur = row.get("market_implied_probability")
        if cur is None:
            cur = price_to_implied(row.get("price"))
        try:
            cur_f = float(cur) if cur is not None else None
        except (TypeError, ValueError):
            cur_f = None
        if key in prior and cur_f is not None and 0.0 < cur_f < 1.0:
            prev = float(prior[key])
            row["odds_delta"] = round(cur_f - prev, 6)
            row["odds_delta_source"] = "temporal_snapshot"
            hist = list(row.get("odds_history") or [])
            hist = [
                {
                    "implied_probability": prev,
                    "source": "prior_snapshot",
                },
                *hist,
            ]
            row["odds_history"] = hist
        out.append(row)
    return out


def collect_current_implieds(markets: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    snaps: dict[str, float] = {}
    for m in markets:
        if not isinstance(m, Mapping):
            continue
        key = _stable_line_key(m)
        if not key or key.startswith("|"):
            continue
        imp = m.get("market_implied_probability")
        if imp is None:
            imp = price_to_implied(m.get("price"))
        try:
            imp_f = float(imp) if imp is not None else None
        except (TypeError, ValueError):
            imp_f = None
        if imp_f is not None and 0.0 < imp_f < 1.0:
            snaps[key] = imp_f
    return snaps


def enrich_markets_odds_movement(
    markets: Sequence[Mapping[str, Any]],
    *,
    data_root: Path | str | None = None,
    persist_snapshot: bool = True,
) -> list[dict[str, Any]]:
    """Full enrichment: cross-book then optional temporal snapshot merge."""
    enriched = enrich_markets_cross_book(markets)
    if data_root is None:
        return enriched
    prior = load_implied_snapshots(data_root)
    if prior:
        enriched = apply_temporal_delta(enriched, prior)
    if persist_snapshot:
        # Merge current into prior map (update lines we saw)
        merged = dict(prior)
        merged.update(collect_current_implieds(enriched))
        save_implied_snapshots(data_root, merged)
    return enriched


def enrich_event_markets(
    event: Mapping[str, Any],
    *,
    data_root: Path | str | None = None,
    persist_snapshot: bool = True,
) -> dict[str, Any]:
    """Copy event with enriched markets list."""
    out = dict(event)
    markets = [m for m in (event.get("markets") or []) if isinstance(m, Mapping)]
    if not markets:
        return out
    # Ensure event_id on markets for grouping
    eid = str(event.get("event_id") or "")
    tagged = []
    for m in markets:
        row = dict(m)
        if eid and not row.get("event_id"):
            row["event_id"] = eid
        tagged.append(row)
    out["markets"] = enrich_markets_odds_movement(
        tagged, data_root=data_root, persist_snapshot=persist_snapshot
    )
    return out
