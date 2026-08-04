"""Full operator day closed loop: fixture → ingest → compete → paper → settle → perf → promo → dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from hollersports.governance.authority import assert_no_live_capital
from hollersports.paper.reliability_ledger import record_reliability_from_settlements
from hollersports.pipelines.market_ingestion import run_market_ingestion
from hollersports.pipelines.paper_loop import run_paper_loop
from hollersports.pipelines.strategy_competition import run_strategy_competition
from hollersports.runes.operator_project import project_dashboard
from hollersports.runes.performance_tracker import compute_performance
from hollersports.runes.promotion_evaluator import evaluate_promotion
from hollersports.runes.settlement_engine import settle_entry
from hollersports.sources.fixture_adapter import load_fixture_day

# All gates True for fixture paper path.
_FIXTURE_GATES: dict[str, bool] = {
    "source_health_gate": True,
    "governance_gate": True,
    "truth_gate": True,
    "liquidity_gate": True,
    "bankroll_gate": True,
}

_DEFAULT_BANKROLL = 1000.0
_DEFAULT_HUMAN_MAX_STAKE = 25.0
_TOP_N = 5


def _load_results(fixture_dir: Path) -> list[dict[str, Any]]:
    path = fixture_dir / "results.json"
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict):
        results = raw.get("results")
        if isinstance(results, list):
            return [r for r in results if isinstance(r, dict)]
        # Single keyed map: {market_id: {...}} or {event_id: {...}}
        if all(isinstance(v, dict) for v in raw.values()):
            out: list[dict[str, Any]] = []
            for key, val in raw.items():
                if key in {"schema_version", "meta"}:
                    continue
                row = dict(val)
                row.setdefault("market_id", key)
                out.append(row)
            return out
    return []


def _index_results(
    results: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Index by (event_id, market_id) and (market_id, '') for flexible lookup."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for r in results:
        eid = str(r.get("event_id") or "")
        mid = str(r.get("market_id") or "")
        if mid:
            index[(eid, mid)] = r
            index[("", mid)] = r
        if eid and not mid:
            index[(eid, "")] = r
    return index


def _lookup_result(
    index: dict[tuple[str, str], dict[str, Any]],
    event_id: str,
    market_id: str,
) -> dict[str, Any] | None:
    eid = str(event_id or "")
    mid = str(market_id or "")
    if (eid, mid) in index:
        return index[(eid, mid)]
    if mid and ("", mid) in index:
        return index[("", mid)]
    if eid and (eid, "") in index:
        return index[(eid, "")]
    return None


def _market_price_map(ingest: Mapping[str, Any]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for m in ingest.get("markets") or []:
        if not isinstance(m, Mapping):
            continue
        mid = str(m.get("market_id") or "")
        if mid and m.get("price") is not None:
            try:
                prices[mid] = float(m["price"])
            except (TypeError, ValueError):
                continue
    return prices


def _top_candidates(
    candidates: list[Mapping[str, Any]],
    n: int,
    prices: dict[str, float],
) -> list[dict[str, Any]]:
    ranked = sorted(
        candidates,
        key=lambda c: float(c.get("score") or 0.0),
        reverse=True,
    )
    top = ranked[: max(0, n)]
    enriched: list[dict[str, Any]] = []
    for c in top:
        row = dict(c)
        mid = str(row.get("market_id") or "")
        if row.get("price") is None and mid in prices:
            row["price"] = prices[mid]
        enriched.append(row)
    return enriched


def run_operator_day(
    fixture_dir: Path | str | None,
    *,
    data_root: Path | str,
) -> dict[str, Any]:
    """Run a full closed-loop operator day against a fixture directory.

    Sequence:
      1. load fixture → ingest
      2. compete
      3. paper top-N candidates (all gates True for fixture)
      4. settle via results.json
      5. performance + promotion
      6. dashboard projection

    Return keys (stable for API/UI):
      ingest, competition, paper, settlements, performance, promotion, dashboard
    """
    root = Path(data_root)
    root.mkdir(parents=True, exist_ok=True)

    if fixture_dir is None:
        raise ValueError("fixture_dir is required for v1 operator day")
    day_path = Path(fixture_dir)

    day = load_fixture_day(day_path)
    ingest = run_market_ingestion(day["ingest_payload"])
    run_id = str(ingest.get("run_id") or day.get("meta", {}).get("run_id") or "UNKNOWN")
    portfolio_id = "default"

    competition = run_strategy_competition(ingest)

    cand_list: list[Mapping[str, Any]] = [
        c
        for c in (competition.get("candidates") or [])
        if isinstance(c, Mapping) and c.get("status") == "CANDIDATE"
    ]
    prices = _market_price_map(ingest)
    n = min(_TOP_N, len(cand_list))
    paper_candidates = _top_candidates(cand_list, n, prices)

    ledger_file = root / "ledgers" / f"{portfolio_id}.jsonl"
    paper_context: dict[str, Any] = {
        "run_id": run_id,
        "portfolio_id": portfolio_id,
        "bankroll": _DEFAULT_BANKROLL,
        "human_max_stake": _DEFAULT_HUMAN_MAX_STAKE,
        "gates": dict(_FIXTURE_GATES),
        "ledger_path": ledger_file,
    }
    paper = run_paper_loop(paper_candidates, paper_context)

    results_index = _index_results(_load_results(day_path))
    settlement_entries: list[dict[str, Any]] = []
    for entry in paper.get("ledger_entries") or paper.get("portfolio_entries") or []:
        if not isinstance(entry, Mapping):
            continue
        # Normalize stake field for settle_entry.
        settle_input = dict(entry)
        if "stake" not in settle_input and "paper_stake" in settle_input:
            settle_input["stake"] = settle_input["paper_stake"]
        result = _lookup_result(
            results_index,
            str(entry.get("event_id") or ""),
            str(entry.get("market_id") or ""),
        )
        settlement_entries.append(settle_entry(settle_input, result))

    settlements: dict[str, Any] = {
        "schema_version": "SettlementBatch.v1",
        "status": "COMPUTED",
        "run_id": run_id,
        "entries": settlement_entries,
        "count": len(settlement_entries),
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
    }

    performance = compute_performance(settlement_entries)

    # Fixture-day evidence: small sample expected → BLOCKED.
    source_health = ingest.get("source_health") or {}
    health_status = str(source_health.get("status") or "")
    evidence: dict[str, Any] = {
        "target_id": portfolio_id,
        "target_type": "PORTFOLIO",
        "source_health_pass_rate": 1.0 if health_status in {"PASS", "WARN"} else 0.0,
        "invariance_pass": True,
        "regimes": 1,
        "market_types": len(
            {
                str(m.get("market_type") or "")
                for m in (ingest.get("markets") or [])
                if isinstance(m, Mapping)
            }
        ),
        "unresolved_blockers": 0,
    }
    promotion = evaluate_promotion(performance, evidence)

    # Append reliability snapshot once per operator-day settle (no double-append
    # with /runs/settle unless that route is called again on the same day).
    record_reliability_from_settlements(root, settlement_entries)

    dashboard = project_dashboard(
        {
            "run_id": run_id,
            "portfolio_id": portfolio_id,
            "ingest": ingest,
            "paper": paper,
            "settlements": settlements,
            "performance": performance,
            "promotion": promotion,
            "sources": {
                "source_id": ingest.get("source_id") or "FIXTURE",
                "source_health": source_health,
                "status": ingest.get("status"),
            },
        }
    )

    out: dict[str, Any] = {
        "ingest": ingest,
        "competition": competition,
        "paper": paper,
        "settlements": settlements,
        "performance": performance,
        "promotion": promotion,
        "dashboard": dashboard,
    }
    for key in ("ingest", "competition", "paper", "settlements", "performance", "promotion", "dashboard"):
        packet = out[key]
        if isinstance(packet, Mapping):
            assert_no_live_capital(packet)
    assert "Place bet" not in str(out)
    return out
