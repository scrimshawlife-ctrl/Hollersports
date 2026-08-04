"""FastAPI routes for paper-only operator day packets (§5.6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from hollersports.api.deps import RunStore, resolve_fixture_dir
from hollersports.governance.authority import assert_no_live_capital
from hollersports.pipelines.market_ingestion import run_market_ingestion
from hollersports.pipelines.paper_loop import run_paper_loop
from hollersports.pipelines.strategy_competition import run_strategy_competition
from hollersports.runes.operator_project import project_dashboard
from hollersports.runes.performance_tracker import compute_performance
from hollersports.runes.promotion_evaluator import evaluate_promotion
from hollersports.runes.settlement_engine import settle_entry
from hollersports.sources.fixture_adapter import load_fixture_day
from hollersports.sources.registry import list_sources, load_registry

router = APIRouter(prefix="/v1")

_DEFAULT_BANKROLL = 1000.0
_DEFAULT_HUMAN_MAX_STAKE = 25.0
_TOP_N = 5
_FIXTURE_GATES: dict[str, bool] = {
    "source_health_gate": True,
    "governance_gate": True,
    "truth_gate": True,
    "liquidity_gate": True,
    "bankroll_gate": True,
}


class IngestRequest(BaseModel):
    fixture: str | None = Field(default=None, description="Fixture day name, e.g. day001")
    payload: dict[str, Any] | None = Field(
        default=None, description="Optional raw ingest payload (non-fixture)"
    )


class EmptyRunRequest(BaseModel):
    """Optional body for compete/paper/settle; currently unused fields reserved."""

    portfolio_id: str | None = "default"


def _store(request: Request) -> RunStore:
    return request.app.state.store  # type: ignore[no-any-return]


def _safe_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Enforce v1 authority locks before returning any packet."""
    assert_no_live_capital(packet)
    if packet.get("mode") == "LIVE_APPROVED":
        raise ValueError("LIVE_APPROVED mode forbidden in v1")
    # Never leak live UX labels.
    if "Place bet" in str(packet):
        raise ValueError("live betting UX forbidden in packet")
    return packet


def _market_price_map(ingest: dict[str, Any] | None) -> dict[str, float]:
    prices: dict[str, float] = {}
    if not isinstance(ingest, dict):
        return prices
    for m in ingest.get("markets") or []:
        if not isinstance(m, dict):
            continue
        mid = str(m.get("market_id") or "")
        if mid and m.get("price") is not None:
            try:
                prices[mid] = float(m["price"])
            except (TypeError, ValueError):
                continue
    return prices


def _top_candidates(
    candidates: list[dict[str, Any]],
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


def _rebuild_dashboard(store: RunStore) -> dict[str, Any]:
    ingest = store.get("ingest") or {}
    run_id = "UNKNOWN"
    if isinstance(ingest, dict):
        run_id = str(ingest.get("run_id") or "UNKNOWN")
    paper = store.get("paper") or {}
    if isinstance(paper, dict) and paper.get("run_id"):
        run_id = str(paper.get("run_id") or run_id)
    source_health = {}
    if isinstance(ingest, dict):
        source_health = ingest.get("source_health") or {}
    dashboard = project_dashboard(
        {
            "run_id": run_id,
            "portfolio_id": "default",
            "ingest": ingest if isinstance(ingest, dict) else {},
            "paper": paper if isinstance(paper, dict) else {},
            "settlements": store.get("settlements") or {},
            "performance": store.get("performance") or {},
            "promotion": store.get("promotion") or {},
            "sources": {
                "source_id": (ingest.get("source_id") if isinstance(ingest, dict) else None)
                or "FIXTURE",
                "source_health": source_health,
                "status": ingest.get("status") if isinstance(ingest, dict) else None,
            },
        }
    )
    store.put("dashboard", dashboard)
    return dashboard


@router.get("/health")
def health() -> dict[str, Any]:
    """API + source registry summary. Never grants capital authority."""
    try:
        reg = load_registry()
        sources = list_sources(reg)
    except Exception:  # noqa: BLE001 — health must not fail closed on registry IO
        sources = []
    body: dict[str, Any] = {
        "schema_version": "HealthPacket.v1",
        "status": "OK",
        "capital_authority": False,
        "execution_authority": False,
        "authority": "PROJECTION_ONLY",
        "mode": "PAPER_ONLY",
        "sources": [
            {
                "id": s.get("id"),
                "type": s.get("type"),
                "enabled": s.get("enabled", True),
            }
            for s in sources
        ],
        "source_count": len(sources),
        "provenance": {"live_mode": False},
    }
    return _safe_packet(body)


@router.post("/runs/ingest")
def runs_ingest(body: IngestRequest, request: Request) -> dict[str, Any]:
    """Source fetch + health + ingest (fixture day or raw payload)."""
    store = _store(request)
    fixture_name = body.fixture
    fixture_dir: Path | None = None

    if fixture_name:
        try:
            fixture_dir = resolve_fixture_dir(fixture_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        day = load_fixture_day(fixture_dir)
        payload = day["ingest_payload"]
        store.update(
            fixture=str(fixture_dir),
            meta=day.get("meta") or {"fixture": fixture_name},
        )
    elif body.payload:
        payload = body.payload
    else:
        raise HTTPException(
            status_code=400,
            detail="fixture or payload is required",
        )

    ingest = run_market_ingestion(payload)
    store.put("ingest", ingest)
    # Clear downstream packets so dashboard reflects current step.
    store.update(
        competition=None,
        paper=None,
        settlements=None,
        performance=None,
        promotion=None,
    )
    _rebuild_dashboard(store)
    return _safe_packet(ingest)


@router.post("/runs/compete")
def runs_compete(
    request: Request,
    body: EmptyRunRequest | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """Strategy competition on last ingest."""
    store = _store(request)
    ingest = store.get("ingest")
    competition = run_strategy_competition(ingest if isinstance(ingest, dict) else None)
    store.put("competition", competition)
    _rebuild_dashboard(store)
    return _safe_packet(competition)


@router.post("/runs/paper")
def runs_paper(
    request: Request,
    body: EmptyRunRequest | None = None,
) -> dict[str, Any]:
    """Guard → construct → paper ledger for top-N candidates."""
    store = _store(request)
    portfolio_id = "default"
    if body and body.portfolio_id:
        portfolio_id = str(body.portfolio_id)

    competition = store.get("competition") or {}
    ingest = store.get("ingest") or {}
    cand_list: list[dict[str, Any]] = []
    if isinstance(competition, dict):
        for c in competition.get("candidates") or []:
            if isinstance(c, dict) and c.get("status") == "CANDIDATE":
                cand_list.append(c)

    prices = _market_price_map(ingest if isinstance(ingest, dict) else None)
    n = min(_TOP_N, len(cand_list))
    paper_candidates = _top_candidates(cand_list, n, prices)

    run_id = "UNKNOWN"
    if isinstance(ingest, dict):
        run_id = str(ingest.get("run_id") or "UNKNOWN")
    if isinstance(competition, dict) and competition.get("run_id"):
        run_id = str(competition.get("run_id") or run_id)

    paper_context: dict[str, Any] = {
        "run_id": run_id,
        "portfolio_id": portfolio_id,
        "bankroll": _DEFAULT_BANKROLL,
        "human_max_stake": _DEFAULT_HUMAN_MAX_STAKE,
        "gates": dict(_FIXTURE_GATES),
        "ledger_path": store.ledger_path(portfolio_id),
    }
    paper = run_paper_loop(paper_candidates, paper_context)
    store.put("paper", paper)
    _rebuild_dashboard(store)
    return _safe_packet(paper)


@router.post("/runs/settle")
def runs_settle(
    request: Request,
    body: EmptyRunRequest | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """Attach fixture results + settle paper entries → performance + promotion."""
    store = _store(request)
    paper = store.get("paper") or {}
    ingest = store.get("ingest") or {}
    run_id = "UNKNOWN"
    if isinstance(paper, dict) and paper.get("run_id"):
        run_id = str(paper.get("run_id") or "UNKNOWN")
    elif isinstance(ingest, dict):
        run_id = str(ingest.get("run_id") or "UNKNOWN")

    fixture_raw = store.get("fixture")
    results_index: dict[tuple[str, str], dict[str, Any]] = {}
    if fixture_raw:
        try:
            results_index = _index_results(_load_results(Path(str(fixture_raw))))
        except OSError:
            results_index = {}

    entries_src: list[Any] = []
    if isinstance(paper, dict):
        entries_src = list(
            paper.get("ledger_entries") or paper.get("portfolio_entries") or []
        )

    settlement_entries: list[dict[str, Any]] = []
    for entry in entries_src:
        if not isinstance(entry, dict):
            continue
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
    store.put("settlements", settlements)

    performance = compute_performance(settlement_entries)
    store.put("performance", performance)

    portfolio_id = "default"
    source_health: dict[str, Any] = {}
    if isinstance(ingest, dict):
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
                for m in (ingest.get("markets") or [] if isinstance(ingest, dict) else [])
                if isinstance(m, dict)
            }
        ),
        "unresolved_blockers": 0,
    }
    promotion = evaluate_promotion(performance, evidence)
    store.put("promotion", promotion)

    _rebuild_dashboard(store)
    return _safe_packet(settlements)


@router.get("/dashboard")
def get_dashboard(request: Request) -> dict[str, Any]:
    """Latest operator dashboard packet (PROJECTION_ONLY)."""
    store = _store(request)
    existing = store.get("dashboard")
    if isinstance(existing, dict) and existing.get("authority") == "PROJECTION_ONLY":
        return _safe_packet(existing)
    dashboard = _rebuild_dashboard(store)
    return _safe_packet(dashboard)


@router.get("/portfolio")
def get_portfolio(request: Request) -> dict[str, Any]:
    """Paper book + performance projection."""
    store = _store(request)
    paper = store.get("paper") if isinstance(store.get("paper"), dict) else {}
    performance = (
        store.get("performance") if isinstance(store.get("performance"), dict) else {}
    )
    settlements = (
        store.get("settlements") if isinstance(store.get("settlements"), dict) else {}
    )
    run_id = str(
        (paper or {}).get("run_id")
        or (performance or {}).get("run_id")
        or "UNKNOWN"
    )
    body: dict[str, Any] = {
        "schema_version": "PaperPortfolioPacket.v1",
        "status": paper.get("status") if paper else "EMPTY",
        "run_id": run_id,
        "portfolio_id": paper.get("portfolio_id") or "default",
        "paper": paper or {},
        "performance": performance or {},
        "settlements": settlements or {},
        "ledger_entries": list((paper or {}).get("ledger_entries") or []),
        "portfolio_entries": list((paper or {}).get("portfolio_entries") or []),
        "authority": "PROJECTION_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "provenance": {"mode": "PAPER_ONLY", "live_mode": False},
    }
    return _safe_packet(body)


@router.get("/promotion")
def get_promotion(request: Request) -> dict[str, Any]:
    """Promotion gate status for last settled run."""
    store = _store(request)
    promotion = store.get("promotion")
    if isinstance(promotion, dict):
        return _safe_packet(promotion)
    # Empty projection when settle has not run.
    body: dict[str, Any] = {
        "schema_version": "PromotionPacket.v1",
        "status": "BLOCKED",
        "target_id": "default",
        "target_type": "PORTFOLIO",
        "passed_gates": [],
        "failed_gates": ["no_settlement_run"],
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "provenance": {"mode": "PAPER_ONLY"},
    }
    return _safe_packet(body)
