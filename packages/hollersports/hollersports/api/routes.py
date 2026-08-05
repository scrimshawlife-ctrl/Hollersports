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
from hollersports.pipelines.operator_day import run_operator_day
from hollersports.pipelines.free_first_day import run_free_first_operator_day
from hollersports.pipelines.paper_loop import run_paper_loop
from hollersports.pipelines.strategy_competition import (
    run_strategy_competition,
    run_strategy_competition_multi,
)
from hollersports.runes.operator_project import project_dashboard
from hollersports.runes.performance_tracker import compute_performance
from hollersports.runes.promotion_evaluator import evaluate_promotion
from hollersports.paper.reliability_ledger import (
    read_reliability_history,
    record_reliability_from_settlements,
    reliability_ledger_path,
)
from hollersports.paper.settlement_history import (
    append_settlement_history,
    calibration_entries_for_store,
    read_settlement_history,
)
from hollersports.runes.calibration_evaluator import (
    calibration_gate_from_packet,
    evaluate_calibration,
)
from hollersports.runes.reliability_bucket import compute_reliability_buckets
from hollersports.runes.settlement_engine import settle_entry
from hollersports.sources.fixture_adapter import load_fixture_day
from hollersports.sources.free_first_ingest import build_live_observation_pack
from hollersports.sources.espn_outcomes import (
    merge_espn_moneyline_results,
    normalize_espn_moneyline_results,
)
from hollersports.sources.espn_scoreboard import ESPN_LEAGUE_PATHS, fetch_espn_scoreboard
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
    """Optional body for compete/settle; portfolio reserved."""

    portfolio_id: str | None = "default"


class CompeteRequest(BaseModel):
    """Strategy competition options (advisory; no money).

    Model edge stays offline unless allow_forecast_weighting and
    reliability_status == RELIABLE (see calibration_allows_model_edge).

    When use_auto_calibration is true, reliability_status is derived from
    settled paper outcomes via evaluate_calibration (evidence ladder).
    """

    portfolio_id: str | None = "default"
    allow_forecast_weighting: bool = Field(
        default=False,
        description="When true with RELIABLE status, load MODEL_PROBABILITY_EDGE",
    )
    reliability_status: str = Field(
        default="UNRELIABLE",
        description="Manual status when use_auto_calibration is false",
    )
    use_auto_calibration: bool = Field(
        default=False,
        description="Derive reliability_status from last settlements (evidence)",
    )


class PaperRunRequest(BaseModel):
    """Paper simulation of advised tickets (no real money)."""

    portfolio_id: str | None = "default"
    candidate_ids: list[str] | None = Field(
        default=None,
        description="Optional strategy+market keys; default top-N by score",
    )


class FullDayRequest(BaseModel):
    fixture: str = Field(default="day001", description="Fixture day name")


class SettleRequest(BaseModel):
    """Settle paper entries. Fixture results preferred; free-first may inject ESPN."""

    results: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional injected result rows (tests / offline). Fail-closed otherwise.",
    )
    espn_raw: dict[str, Any] | None = Field(
        default=None,
        description="Injected ESPN scoreboard JSON for free-first finals (CI-safe).",
    )
    leagues: list[str] | None = Field(
        default=None,
        description="Leagues for espn_raw / optional live fetch (default NBA when raw set).",
    )
    fetch_espn: bool = Field(
        default=False,
        description="Opt-in live ESPN fetch when no fixture/results/injection (never required).",
    )


class FreeFirstRequest(BaseModel):
    """Optional live observation (advisory). Prefer injected raw in tests."""

    espn_only: bool = False
    odds_only: bool = False
    run_id: str | None = None
    # Test/offline injection — never required for CI
    espn_raw: dict[str, Any] | None = None
    odds_raw: list[dict[str, Any]] | None = None
    leagues: list[str] | None = Field(
        default=None,
        description=(
            "Day-one leagues to observe (NBA, NFL, MLB, NHL, MLS, EPL). "
            "Omit for all leagues on live fetch; injected raw defaults to NBA."
        ),
    )
    auto_compete: bool = Field(
        default=True,
        description="If ingest succeeds, run strategy competition on primary ingest",
    )


class FreeFirstDayRequest(BaseModel):
    """Closed free-first day into the calibration bank (advisory only)."""

    run_id: str | None = None
    leagues: list[str] | None = Field(
        default=None,
        description="Day-one leagues; omit for live all / injected NBA default.",
    )
    espn_raw: dict[str, Any] | None = None
    odds_raw: list[dict[str, Any]] | None = None
    settle_espn_raw: dict[str, Any] | None = Field(
        default=None,
        description="Injected ESPN finals scoreboard for settle (CI-safe).",
    )
    espn_only: bool = False
    odds_only: bool = False
    fetch_espn_finals: bool = Field(
        default=False,
        description="Opt-in live ESPN finals fetch when settle_espn_raw omitted.",
    )
    paper_top_n: int = Field(default=20, ge=0, le=200)


class MlTrainRequest(BaseModel):
    """Train + calibrate baseline ensemble from fixture days (advisory offline)."""

    train_fixtures: list[str] = Field(
        default_factory=lambda: ["day001", "day002"],
        description="Fixture day names (e.g. day001, day002)",
    )
    val_fixtures: list[str] | None = Field(
        default=None,
        description="Optional validation fixture days; omit for auto split / identity T",
    )
    seed: int = 42
    prefer_sklearn: bool = Field(
        default=False,
        description="Use sklearn HGB when [ml] extra installed; else logistic",
    )


class MlAnnotateRequest(BaseModel):
    """Annotate last ingest markets with ensemble model_probability (fail closed)."""

    ensemble_path: str | None = Field(
        default=None,
        description="Optional path to ensemble.json; default last train / data_root/ml/ensemble.json",
    )
    ev_threshold: float = Field(default=0.03, ge=0.0, le=1.0)
    auto_compete: bool = Field(
        default=False,
        description="If true, run strategy competition after annotate",
    )
    allow_forecast_weighting: bool = Field(
        default=False,
        description="With RELIABLE (or override), load MODEL_PROBABILITY_EDGE on auto_compete",
    )
    reliability_status: str = Field(
        default="UNRELIABLE",
        description="Manual calibration status when auto_compete and not use_auto_calibration",
    )
    use_auto_calibration: bool = False


class MlRetrainCheckRequest(BaseModel):
    """Advisory retrain proposal from ensemble + labeled fixtures (never auto-trains)."""

    ensemble_path: str | None = Field(
        default=None,
        description="Optional ensemble.json; default last train / data_root/ml/ensemble.json",
    )
    eval_fixtures: list[str] = Field(
        default_factory=lambda: ["day001", "day002", "day003"],
        description="Fixture days with results for Brier evaluation",
    )
    brier_degrade: float = Field(default=0.01, ge=0.0, le=1.0)
    min_labeled: int = Field(default=8, ge=1, le=10_000)


class MlRetrainApplyRequest(BaseModel):
    """Human/Hermes-gated retrain: requires explicit confirm (never silent)."""

    confirm: bool = Field(
        default=False,
        description="Must be true to train; refuse otherwise",
    )
    require_suggestion: bool = Field(
        default=True,
        description="If true, last retrain-check must be RETRAIN_SUGGESTED",
    )
    train_fixtures: list[str] = Field(
        default_factory=lambda: ["day001", "day002", "day003"],
        description="Fixture days to retrain on",
    )
    seed: int = 42
    prefer_sklearn: bool = False


def _store(request: Request) -> RunStore:
    return request.app.state.store  # type: ignore[no-any-return]


def _safe_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Enforce v1 authority locks before returning any packet.

    Authority / live-mode violations fail closed as HTTP 403 (not 500).
    """
    try:
        assert_no_live_capital(packet)
        if packet.get("mode") == "LIVE_APPROVED":
            raise ValueError("LIVE_APPROVED mode forbidden in v1")
        # Never leak live UX labels.
        if "Place bet" in str(packet):
            raise ValueError("live betting UX forbidden in packet")
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=f"authority lock: {exc}",
        ) from exc
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


def _merged_market_price_map(
    ingest: dict[str, Any] | None,
    ingests: list[dict[str, Any]] | None = None,
) -> dict[str, float]:
    """Union market prices across free-first multi-event ingests (primary first)."""
    prices: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    if ingests:
        rows.extend(i for i in ingests if isinstance(i, dict))
    elif isinstance(ingest, dict):
        rows.append(ingest)
    # If both present, prefer full slate then fill gaps from primary.
    if ingests and isinstance(ingest, dict) and ingest not in rows:
        rows.append(ingest)
    for row in rows:
        for mid, price in _market_price_map(row).items():
            prices.setdefault(mid, price)
    return prices


def _stored_ingests(store: RunStore) -> list[dict[str, Any]]:
    raw = store.get("ingests")
    if isinstance(raw, list):
        return [i for i in raw if isinstance(i, dict)]
    ingest = store.get("ingest")
    if isinstance(ingest, dict):
        return [ingest]
    return []


def _any_source_health_fail(ingests: list[dict[str, Any]]) -> bool:
    for ingest in ingests:
        source_health = ingest.get("source_health") or {}
        if isinstance(source_health, dict) and str(source_health.get("status") or "") == "FAIL":
            return True
    return False


def _expand_results_via_ingest_joins(
    results: list[dict[str, Any]],
    ingests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Duplicate ESPN result rows under joined odds event_ids when present.

    Free-first prefers odds ``event_id`` on candidates; ESPN finals use schedule
    ids. Join meta on ingest ``source_refs.join`` maps left (ESPN) ↔ right (odds).
    """
    if not results or not ingests:
        return list(results)
    alias: dict[str, set[str]] = {}
    for ing in ingests:
        refs = ing.get("source_refs") if isinstance(ing.get("source_refs"), dict) else {}
        join = refs.get("join") if isinstance(refs.get("join"), dict) else {}
        left = str(join.get("left_event_id") or "")
        right = str(join.get("right_event_id") or "")
        payload_eid = str((ing.get("payload") or {}).get("event_id") or ing.get("event_id") or "")
        # Market packets use top-level event_id after ingest.
        top_eid = str(ing.get("event_id") or "")
        for a, b in ((left, right), (right, left), (left, top_eid), (left, payload_eid)):
            if a and b and a != b:
                alias.setdefault(a, set()).add(b)
                alias.setdefault(b, set()).add(a)
    if not alias:
        return list(results)
    expanded = list(results)
    for row in results:
        eid = str(row.get("event_id") or "")
        for alt in alias.get(eid, ()):
            copy = dict(row)
            copy["event_id"] = alt
            copy.setdefault("provenance", {})
            if isinstance(copy["provenance"], dict):
                prov = dict(copy["provenance"])
                prov["aliased_from_event_id"] = eid
                copy["provenance"] = prov
            expanded.append(copy)
    return expanded


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
        sel = str(r.get("selection") or "")
        if mid:
            index[(eid, mid)] = r
            index[("", mid)] = r
        if eid and not mid:
            index[(eid, "")] = r
        if eid and sel:
            index[(eid, f"sel:{sel}")] = r
            index[(eid, f"sel:{sel.upper()}")] = r
    return index


def _lookup_result(
    index: dict[tuple[str, str], dict[str, Any]],
    event_id: str,
    market_id: str,
    selection: str = "",
) -> dict[str, Any] | None:
    eid = str(event_id or "")
    mid = str(market_id or "")
    sel = str(selection or "")
    if (eid, mid) in index:
        return index[(eid, mid)]
    if mid and ("", mid) in index:
        return index[("", mid)]
    if eid and sel:
        for key in ((eid, f"sel:{sel}"), (eid, f"sel:{sel.upper()}")):
            if key in index:
                return index[key]
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
    meta = store.get("meta") if isinstance(store.get("meta"), dict) else {}
    competition = (
        store.get("competition") if isinstance(store.get("competition"), dict) else {}
    )
    ingests = _stored_ingests(store)
    slate = {
        "path": meta.get("path"),
        "ingest_count": meta.get("ingest_count")
        if meta.get("ingest_count") is not None
        else len(ingests),
        "competed_event_count": competition.get("competed_event_count"),
        "candidate_count": competition.get("candidate_count"),
        "competition_status": competition.get("status"),
        "conflict_status": meta.get("conflict_status"),
    }
    dashboard = project_dashboard(
        {
            "run_id": run_id,
            "portfolio_id": "default",
            "ingest": ingest if isinstance(ingest, dict) else {},
            "paper": paper if isinstance(paper, dict) else {},
            "settlements": store.get("settlements") or {},
            "performance": store.get("performance") or {},
            "promotion": store.get("promotion") or {},
            "slate": slate,
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
        ingests=None,
        competition=None,
        paper=None,
        settlements=None,
        performance=None,
        promotion=None,
    )
    _rebuild_dashboard(store)
    return _safe_packet(ingest)


def _settlement_entries(store: RunStore) -> list[dict[str, Any]]:
    """Cumulative settlement bank when present; else last batch only."""
    last: list[dict[str, Any]] = []
    settlements = store.get("settlements")
    if isinstance(settlements, dict):
        last = [e for e in (settlements.get("entries") or []) if isinstance(e, dict)]
    return calibration_entries_for_store(store.data_root, last)


@router.post("/runs/compete")
def runs_compete(
    request: Request,
    body: CompeteRequest | EmptyRunRequest | None = None,
) -> dict[str, Any]:
    """Strategy competition on last ingest.

    Optional calibration (CompeteRequest) gates MODEL_PROBABILITY_EDGE.
    Default body / EmptyRunRequest → model edge off.
    """
    store = _store(request)
    ingest = store.get("ingest")
    ingests = _stored_ingests(store)
    calibration: dict[str, Any] | None = None
    if isinstance(body, CompeteRequest):
        allow = bool(body.allow_forecast_weighting)
        if body.use_auto_calibration:
            cal_packet = evaluate_calibration(
                _settlement_entries(store),
                allow_forecast_weighting=allow,
            )
            store.put("calibration", cal_packet)
            calibration = calibration_gate_from_packet(cal_packet)
        else:
            calibration = {
                "allow_forecast_weighting": allow,
                "reliability_status": str(body.reliability_status or "UNRELIABLE"),
            }
            store.put("calibration", calibration)
    if len(ingests) > 1:
        competition = run_strategy_competition_multi(
            ingests,
            calibration=calibration,
            run_id=str((ingest or {}).get("run_id") or "") or None
            if isinstance(ingest, dict)
            else None,
        )
    else:
        competition = run_strategy_competition(
            ingest if isinstance(ingest, dict) else (ingests[0] if ingests else None),
            calibration=calibration,
        )
    store.put("competition", competition)
    _rebuild_dashboard(store)
    return _safe_packet(competition)


def _candidate_key(c: dict[str, Any]) -> str:
    return f"{c.get('strategy_id')}|{c.get('market_id')}|{c.get('selection')}"


@router.get("/candidates")
def get_candidates(request: Request) -> dict[str, Any]:
    """Last competition candidates (advisory projection)."""
    store = _store(request)
    competition = store.get("competition") if isinstance(store.get("competition"), dict) else {}
    candidates = list((competition or {}).get("candidates") or [])
    body: dict[str, Any] = {
        "schema_version": "CandidateListPacket.v1",
        "status": competition.get("status") if competition else "EMPTY",
        "run_id": (competition or {}).get("run_id") or "UNKNOWN",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "authority": "PROJECTION_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
    }
    return _safe_packet(body)


@router.post("/runs/free-first")
def runs_free_first(body: FreeFirstRequest, request: Request) -> dict[str, Any]:
    """Optional live free-first observation pack (advisory only; no money).

    Network is used only when espn_raw/odds_raw are omitted. Without keys/network,
    returns NOT_COMPUTABLE / PARTIAL with errors — never invents odds.
    """
    store = _store(request)
    pack = build_live_observation_pack(
        run_id=body.run_id,
        fetch_espn=not body.odds_only,
        fetch_odds=not body.espn_only,
        espn_raw=body.espn_raw,
        odds_raw=body.odds_raw,
        leagues=body.leagues,
        data_root=str(store.data_root),
        persist_odds_snapshot=True,
    )
    # Store primary + full ingest slate so compete/paper cover all events.
    ingest = pack.get("ingest")
    ingests = [i for i in (pack.get("ingests") or []) if isinstance(i, dict)]
    competition: dict[str, Any] | None = None
    if isinstance(ingest, dict) or ingests:
        for row in ingests:
            assert_no_live_capital(row)
        if isinstance(ingest, dict):
            assert_no_live_capital(ingest)
        store.update(
            ingest=ingest if isinstance(ingest, dict) else (ingests[0] if ingests else None),
            ingests=ingests,
            competition=None,
            paper=None,
            settlements=None,
            performance=None,
            promotion=None,
            meta={
                "path": "free-first",
                "run_id": pack.get("run_id"),
                "ingest_count": pack.get("ingest_count") or len(ingests),
                "conflict_status": (pack.get("conflict") or {}).get("status"),
            },
        )
        if body.auto_compete:
            compete_packets = ingests or ([ingest] if isinstance(ingest, dict) else [])
            competition = run_strategy_competition_multi(
                compete_packets,
                run_id=str(pack.get("run_id") or "") or None,
            )
            store.put("competition", competition)
            pack["competition"] = competition
        _rebuild_dashboard(store)
    summary = {
        "schema_version": "FreeFirstSummary.v1",
        "status": pack.get("status"),
        "run_id": pack.get("run_id"),
        "espn_event_count": pack.get("espn_event_count"),
        "odds_event_count": pack.get("odds_event_count"),
        "ingest_count": pack.get("ingest_count") or len(ingests),
        "competed_event_count": (competition or {}).get("competed_event_count"),
        "candidate_count": (competition or {}).get("candidate_count"),
        "competition_status": (competition or {}).get("status"),
        "conflict_status": (pack.get("conflict") or {}).get("status"),
        "ingest_status": (ingest or {}).get("status") if isinstance(ingest, dict) else None,
        "errors": pack.get("errors") or [],
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "note": "observation_only_no_money",
    }
    return _safe_packet(summary)


@router.post("/runs/free-first-day")
def runs_free_first_day(body: FreeFirstDayRequest, request: Request) -> dict[str, Any]:
    """Closed free-first day: observe → compete → paper → ESPN settle → bank.

    Prefer injected raw for CI. Live finals require ``fetch_espn_finals``.
    Appends to the calibration bank (re-settle-safe collapse on read). Advisory only.
    """
    store = _store(request)
    out = run_free_first_operator_day(
        data_root=store.data_root,
        run_id=body.run_id,
        leagues=body.leagues,
        espn_raw=body.espn_raw,
        odds_raw=body.odds_raw,
        settle_espn_raw=body.settle_espn_raw,
        fetch_espn=not body.odds_only,
        fetch_odds=not body.espn_only,
        fetch_espn_finals=bool(body.fetch_espn_finals) and body.settle_espn_raw is None,
        paper_top_n=body.paper_top_n,
    )
    ingest = out.get("ingest") if isinstance(out.get("ingest"), dict) else None
    ingests = [i for i in (out.get("ingests") or []) if isinstance(i, dict)]
    competition = out.get("competition") if isinstance(out.get("competition"), dict) else None
    paper = out.get("paper") if isinstance(out.get("paper"), dict) else None
    settlements = out.get("settlements") if isinstance(out.get("settlements"), dict) else None
    settlement_entries = list((settlements or {}).get("entries") or [])

    performance = compute_performance(settlement_entries)
    source_health = (ingest or {}).get("source_health") or {}
    health_status = str(source_health.get("status") or "")
    evidence: dict[str, Any] = {
        "target_id": "free-first",
        "target_type": "PORTFOLIO",
        "sample_size": len(settlement_entries),
        "hit_rate": performance.get("hit_rate"),
        "sim_roi": performance.get("sim_roi"),
        "source_health_status": health_status or "UNKNOWN",
        "source_health_pass_rate": 1.0 if health_status in {"PASS", "WARN"} else 0.0,
        "clv_retention": performance.get("clv_retention"),
        "invariance_pass": True,
        "regimes": 1,
        "market_types": 1,
        "unresolved_blockers": 0,
    }
    promotion = evaluate_promotion(performance, evidence)
    if settlement_entries:
        record_reliability_from_settlements(store.data_root, settlement_entries)
    # Bank append already done inside run_free_first_operator_day.

    store.update(
        fixture=None,
        meta={
            "path": "free-first",
            "run_id": out.get("run_id"),
            "ingest_count": out.get("ingest_count") or len(ingests),
            "closed_day": True,
        },
        ingest=ingest or (ingests[0] if ingests else None),
        ingests=ingests,
        competition=competition,
        paper=paper,
        settlements=settlements,
        performance=performance,
        promotion=promotion,
    )
    _rebuild_dashboard(store)

    summary = {
        "schema_version": "FreeFirstDaySummary.v1",
        "status": out.get("status"),
        "run_id": out.get("run_id"),
        "ingest_count": out.get("ingest_count"),
        "competed_event_count": out.get("competed_event_count"),
        "candidate_count": out.get("candidate_count"),
        "paper_status": out.get("paper_status"),
        "paper_approved": out.get("paper_approved"),
        "settlement_count": out.get("settlement_count"),
        "bank_written": out.get("bank_written"),
        "result_count": out.get("result_count"),
        "result_errors": out.get("result_errors") or [],
        "calibration": out.get("calibration"),
        "promotion_status": promotion.get("status"),
        "errors": out.get("errors") or [],
        "authority": "PROJECTION_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "note": "closed_day_no_money",
    }
    return _safe_packet(summary)


@router.post("/runs/full-day")
def runs_full_day(body: FullDayRequest, request: Request) -> dict[str, Any]:
    """One-shot fixture operator day (advisory paper sim; no money)."""
    store = _store(request)
    try:
        fixture_dir = resolve_fixture_dir(body.fixture)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    out = run_operator_day(fixture_dir, data_root=store.data_root)
    store.update(
        fixture=str(fixture_dir),
        meta={"fixture": body.fixture, "path": "full-day"},
        ingest=out.get("ingest"),
        ingests=None,
        competition=out.get("competition"),
        paper=out.get("paper"),
        settlements=out.get("settlements"),
        performance=out.get("performance"),
        promotion=out.get("promotion"),
        dashboard=out.get("dashboard"),
    )
    # Return projection summary without re-emitting full ledger noise
    summary = {
        "schema_version": "FullDaySummary.v1",
        "status": "COMPUTED",
        "fixture": body.fixture,
        "run_id": (out.get("ingest") or {}).get("run_id"),
        "ingest_status": (out.get("ingest") or {}).get("status"),
        "candidate_count": (out.get("competition") or {}).get("candidate_count"),
        "paper_status": (out.get("paper") or {}).get("status"),
        "promotion_status": (out.get("promotion") or {}).get("status"),
        "dashboard_authority": (out.get("dashboard") or {}).get("authority"),
        "authority": "PROJECTION_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
    }
    return _safe_packet(summary)


@router.post("/runs/paper")
def runs_paper(
    request: Request,
    body: PaperRunRequest | EmptyRunRequest | None = None,
) -> dict[str, Any]:
    """Guard → construct → paper ledger for selected or top-N candidates (sim only)."""
    store = _store(request)
    portfolio_id = "default"
    candidate_ids: list[str] | None = None
    if body is not None:
        portfolio_id = str(getattr(body, "portfolio_id", None) or "default")
        raw_ids = getattr(body, "candidate_ids", None)
        if raw_ids:
            candidate_ids = [str(x) for x in raw_ids]

    competition = store.get("competition") or {}
    ingest = store.get("ingest") or {}
    ingests = _stored_ingests(store)
    cand_list: list[dict[str, Any]] = []
    if isinstance(competition, dict):
        for c in competition.get("candidates") or []:
            if isinstance(c, dict) and c.get("status") == "CANDIDATE":
                cand_list.append(c)

    prices = _merged_market_price_map(
        ingest if isinstance(ingest, dict) else None,
        ingests,
    )
    if candidate_ids:
        wanted = set(candidate_ids)
        selected = [c for c in cand_list if _candidate_key(c) in wanted]
        paper_candidates = _top_candidates(selected, len(selected), prices)
    else:
        n = min(_TOP_N, len(cand_list))
        paper_candidates = _top_candidates(cand_list, n, prices)

    run_id = "UNKNOWN"
    if isinstance(ingest, dict):
        run_id = str(ingest.get("run_id") or "UNKNOWN")
    if isinstance(competition, dict) and competition.get("run_id"):
        run_id = str(competition.get("run_id") or run_id)

    # Default open gates for healthy fixture-style paper; fail-closed on
    # source_health FAIL so subsequent /runs/paper rejects rather than simming.
    # Full-day fixture path still opens gates only inside operator_day.
    gates = dict(_FIXTURE_GATES)
    health_rows = list(ingests)
    if isinstance(ingest, dict) and ingest not in health_rows:
        health_rows.append(ingest)
    if _any_source_health_fail(health_rows):
        gates["source_health_gate"] = False

    paper_context: dict[str, Any] = {
        "run_id": run_id,
        "portfolio_id": portfolio_id,
        "bankroll": _DEFAULT_BANKROLL,
        "human_max_stake": _DEFAULT_HUMAN_MAX_STAKE,
        "gates": gates,
        "ledger_path": store.ledger_path(portfolio_id),
    }
    paper = run_paper_loop(paper_candidates, paper_context)
    store.put("paper", paper)
    _rebuild_dashboard(store)
    return _safe_packet(paper)


@router.post("/runs/settle")
def runs_settle(
    request: Request,
    body: SettleRequest | EmptyRunRequest | None = None,
) -> dict[str, Any]:
    """Attach results + settle paper entries → performance + promotion.

    Fixture ``results.json`` when a fixture day is loaded. Free-first may inject
    ``espn_raw`` / ``results`` (CI-safe) or opt into ``fetch_espn``. Missing
    outcomes stay PENDING — never invent winners. Advisory only.
    """
    store = _store(request)
    paper = store.get("paper") or {}
    ingest = store.get("ingest") or {}
    run_id = "UNKNOWN"
    if isinstance(paper, dict) and paper.get("run_id"):
        run_id = str(paper.get("run_id") or "UNKNOWN")
    elif isinstance(ingest, dict):
        run_id = str(ingest.get("run_id") or "UNKNOWN")

    settle_body = body if isinstance(body, SettleRequest) else SettleRequest()
    results_rows: list[dict[str, Any]] = []
    result_errors: list[str] = []

    if settle_body.results:
        results_rows = [r for r in settle_body.results if isinstance(r, dict)]
    else:
        fixture_raw = store.get("fixture")
        if fixture_raw:
            try:
                results_rows = _load_results(Path(str(fixture_raw)))
            except OSError as exc:
                result_errors.append(f"fixture_results:{exc}")
        elif settle_body.espn_raw is not None:
            leagues = settle_body.leagues or ["NBA"]
            for league in leagues:
                try:
                    results_rows.extend(
                        normalize_espn_moneyline_results(
                            settle_body.espn_raw, league=str(league)
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    result_errors.append(f"espn_raw:{league}:{type(exc).__name__}:{exc}")
        elif settle_body.fetch_espn:
            leagues = settle_body.leagues or list(ESPN_LEAGUE_PATHS.keys())
            packs: list[tuple[dict[str, Any], str]] = []
            for league in leagues:
                try:
                    packs.append((fetch_espn_scoreboard(league=str(league)), str(league)))
                except Exception as exc:  # noqa: BLE001
                    result_errors.append(f"espn_fetch:{league}:{type(exc).__name__}:{exc}")
            results_rows = merge_espn_moneyline_results(packs)

    # Free-first: alias ESPN schedule ids → odds event ids via join provenance.
    results_rows = _expand_results_via_ingest_joins(results_rows, _stored_ingests(store))
    results_index = _index_results(results_rows)

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
            str(entry.get("selection") or ""),
        )
        settlement_entries.append(settle_entry(settle_input, result))

    settlements: dict[str, Any] = {
        "schema_version": "SettlementBatch.v1",
        "status": "COMPUTED",
        "run_id": run_id,
        "entries": settlement_entries,
        "count": len(settlement_entries),
        "result_count": len(results_rows),
        "result_errors": result_errors,
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
        "sample_size": len(settlement_entries),
        "hit_rate": performance.get("hit_rate"),
        "sim_roi": performance.get("sim_roi"),
        "source_health_status": health_status or "UNKNOWN",
        "source_health_pass_rate": 1.0 if health_status in {"PASS", "WARN"} else 0.0,
        "clv_retention": performance.get("clv_retention"),
        "calibration_status": (store.get("calibration") or {}).get("status")
        if isinstance(store.get("calibration"), dict)
        else None,
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

    # Append-only reliability + cumulative settlement bank (advice quality).
    record_reliability_from_settlements(store.data_root, settlement_entries)
    fixture_raw = store.get("fixture")
    fixture_name = Path(str(fixture_raw)).name if fixture_raw else None
    append_settlement_history(
        store.data_root,
        settlement_entries,
        run_id=run_id,
        fixture=fixture_name,
    )

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


@router.get("/calibration")
def get_calibration(
    request: Request,
    allow_forecast_weighting: int = 0,
) -> dict[str, Any]:
    """Advice-quality calibration ladder from last settlements (sim only).

    Query ``allow_forecast_weighting=1`` to evaluate whether model edge would
    unlock given current evidence (still requires RELIABLE sample).
    """
    store = _store(request)
    packet = evaluate_calibration(
        _settlement_entries(store),
        allow_forecast_weighting=bool(allow_forecast_weighting),
    )
    return _safe_packet(packet)


@router.get("/reliability")
def get_reliability(
    request: Request,
    history: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """Advice-quality reliability buckets (sim metrics only).

    Default: buckets from last settlements in store.
    ``history=1``: last-N append-only ledger snapshots (oldest-first within window).
    """
    store = _store(request)
    if history:
        lim = max(0, min(int(limit or 20), 200))
        rows = read_reliability_history(
            reliability_ledger_path(store.data_root),
            limit=lim,
        )
        body: dict[str, Any] = {
            "schema_version": "ReliabilityHistoryPacket.v1",
            "status": "COMPUTED" if rows else "EMPTY",
            "entries": rows,
            "count": len(rows),
            "authority": "SHADOW_ONLY",
            "capital_authority": False,
            "execution_authority": False,
            "mode": "ADVISORY_ONLY",
            "provenance": {
                "purpose": "advice_quality_history",
                "real_money": False,
                "order": "oldest_first_within_window",
            },
        }
        return _safe_packet(body)

    settlements = store.get("settlements") if isinstance(store.get("settlements"), dict) else {}
    last = list((settlements or {}).get("entries") or [])
    hist = read_settlement_history(data_root=store.data_root, settled_only=True)
    entries = hist if hist else last
    packet = compute_reliability_buckets(entries)
    packet["provenance"] = {
        **(packet.get("provenance") or {}),
        "source": "cumulative_settlement_history" if hist else "last_settlement_batch",
    }
    return _safe_packet(packet)


def _resolve_ensemble_path(store: RunStore, explicit: str | None) -> Path:
    """Resolve ensemble.json: explicit → store ml_ensemble → data_root/ml/ensemble.json."""
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p.resolve()
        raise FileNotFoundError(f"ensemble not found: {explicit}")
    stored = store.get("ml_ensemble")
    if isinstance(stored, dict) and stored.get("ensemble_path"):
        p = Path(str(stored["ensemble_path"]))
        if p.is_file():
            return p.resolve()
    default = store.data_root / "ml" / "ensemble.json"
    if default.is_file():
        return default.resolve()
    raise FileNotFoundError(
        "no ensemble: POST /v1/ml/train first or pass ensemble_path"
    )


def _annotate_ingest_markets(
    ingest: dict[str, Any],
    ensemble_path: Path,
    *,
    ev_threshold: float,
) -> tuple[dict[str, Any], int]:
    """Return (updated ingest, annotated_count). Markets without features left as-is."""
    from hollersports.ml.apply import apply_ensemble_to_markets

    markets = [m for m in (ingest.get("markets") or []) if isinstance(m, dict)]
    if not markets:
        return ingest, 0
    scored = apply_ensemble_to_markets(
        markets, ensemble_path, ev_threshold=ev_threshold
    )
    by_id = {str(m.get("market_id")): m for m in scored}
    merged = [by_id.get(str(m.get("market_id")) or "") or m for m in markets]
    out = dict(ingest)
    out["markets"] = merged
    prov = dict(out.get("provenance") or {})
    prov["ml_ensemble"] = str(ensemble_path)
    prov["ml_annotated"] = True
    out["provenance"] = prov
    return out, len(scored)


@router.get("/ml/status")
def ml_status(request: Request) -> dict[str, Any]:
    """Last ML train/ensemble path (advisory research tooling)."""
    store = _store(request)
    train = store.get("ml_train") if isinstance(store.get("ml_train"), dict) else {}
    ens = store.get("ml_ensemble") if isinstance(store.get("ml_ensemble"), dict) else {}
    annotate = store.get("ml_annotate") if isinstance(store.get("ml_annotate"), dict) else {}
    retrain = store.get("ml_retrain") if isinstance(store.get("ml_retrain"), dict) else {}
    path = ens.get("ensemble_path") or (store.data_root / "ml" / "ensemble.json")
    path_s = str(path)
    exists = Path(path_s).is_file()
    body = {
        "schema_version": "HollerMlStatus.v1",
        "status": "READY" if exists else "EMPTY",
        "ensemble_path": path_s if exists else None,
        "ensemble_present": exists,
        "last_train": train or None,
        "last_annotate": annotate or None,
        "last_retrain_proposal": retrain or None,
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
    }
    return _safe_packet(body)


@router.get("/ml/model-card")
def ml_model_card(
    request: Request,
    ensemble_path: str | None = None,
) -> dict[str, Any]:
    """Return model card (metrics + markdown) for last or given ensemble."""
    from hollersports.ml.model_card import build_model_card

    store = _store(request)
    try:
        ep = _resolve_ensemble_path(store, ensemble_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        card = build_model_card(ep)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _safe_packet(card)


class MlAxialRequest(BaseModel):
    """Score last ingest with axial backend: torch (preferred) or stdlib stub."""

    backend: str = Field(
        default="auto",
        description="auto | torch | stub — auto uses trained torch weights if present",
    )
    model_meta_path: str | None = Field(
        default=None,
        description="Path to axial_torch.meta.json; default data_root/ml/axial/axial_torch.meta.json",
    )


class MlAxialTrainRequest(BaseModel):
    """Train PyTorch axial model from fixture days (requires torch extra)."""

    train_fixtures: list[str] = Field(
        default_factory=lambda: ["day001", "day002", "day003"]
    )
    epochs: int = Field(default=40, ge=1, le=500)
    seed: int = 42
    lr: float = Field(default=1e-3, gt=0.0)


@router.post("/ml/axial-stub")
def ml_axial_stub(request: Request) -> dict[str, Any]:
    """Backward-compatible stdlib axial stub (see also POST /v1/ml/axial)."""
    return ml_axial(request, MlAxialRequest(backend="stub"))


@router.post("/ml/axial")
def ml_axial(
    request: Request,
    body: MlAxialRequest | None = None,
) -> dict[str, Any]:
    """Score last ingest with PyTorch axial (if available) or stdlib stub.

    Never invents markets; empty ingest → 400. Advisory only.
    """
    from hollersports.ml.axial_stub import markets_to_sequence, score_sequence

    store = _store(request)
    req = body or MlAxialRequest()
    ingest = store.get("ingest")
    if not isinstance(ingest, dict) or ingest.get("status") != "INGESTED":
        raise HTTPException(
            status_code=400,
            detail="no INGESTED run; POST /v1/runs/ingest first",
        )
    markets = [m for m in (ingest.get("markets") or []) if isinstance(m, dict)]
    if not markets:
        raise HTTPException(status_code=400, detail="ingest has no markets")
    seq = markets_to_sequence(markets)

    backend = str(req.backend or "auto").lower()
    meta_path = Path(req.model_meta_path) if req.model_meta_path else (
        store.data_root / "ml" / "axial" / "axial_torch.meta.json"
    )

    packet: dict[str, Any]
    if backend in {"torch", "auto"}:
        try:
            from hollersports.ml.axial_torch import score_sequence_torch, torch_available

            if not torch_available():
                if backend == "torch":
                    raise HTTPException(
                        status_code=503,
                        detail='torch_not_installed: pip install -e "packages/hollersports[torch]"',
                    )
            else:
                path = meta_path if meta_path.is_file() else None
                if path is None and backend == "torch":
                    # Untrained forward still allowed for shape smoke
                    packet = score_sequence_torch(seq, model_meta_path=None)
                else:
                    packet = score_sequence_torch(seq, model_meta_path=path)
                packet["run_id"] = ingest.get("run_id")
                packet["market_count"] = len(markets)
                packet["backend"] = "torch"
                store.put("ml_axial", packet)
                return _safe_packet(packet)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            if backend == "torch":
                raise HTTPException(status_code=400, detail=f"axial_torch:{exc}") from exc
            # auto falls through to stub

    packet = score_sequence(seq)
    packet["run_id"] = ingest.get("run_id")
    packet["market_count"] = len(markets)
    packet["backend"] = "stub"
    store.put("ml_axial", packet)
    return _safe_packet(packet)


@router.post("/ml/axial/train")
def ml_axial_train(body: MlAxialTrainRequest, request: Request) -> dict[str, Any]:
    """Train PyTorch axial model into data_root/ml/axial (requires torch)."""
    store = _store(request)
    try:
        from hollersports.ml.axial_torch import torch_available, train_axial
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not torch_available():
        raise HTTPException(
            status_code=503,
            detail='torch_not_installed: pip install -e "packages/hollersports[torch]"',
        )
    days: list[Path] = []
    for name in body.train_fixtures:
        try:
            days.append(resolve_fixture_dir(name))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    out_dir = store.data_root / "ml" / "axial"
    try:
        result = train_axial(
            days,
            out_dir=out_dir,
            epochs=int(body.epochs),
            seed=int(body.seed),
            lr=float(body.lr),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    packet = {
        "schema_version": "HollerAxialTrainPacket.v1",
        "status": "TRAINED",
        **result,
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
    }
    store.put("ml_axial_train", packet)
    return _safe_packet(packet)


@router.post("/ml/retrain-check")
def ml_retrain_check(
    request: Request,
    body: MlRetrainCheckRequest | None = None,
) -> dict[str, Any]:
    """Evaluate ensemble on labeled fixtures; emit advisory retrain proposal.

    Never trains. Never grants capital/execution authority.
    """
    from hollersports.ml.retrain import propose_retrain

    store = _store(request)
    req = body or MlRetrainCheckRequest()
    try:
        ensemble_path = _resolve_ensemble_path(store, req.ensemble_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    eval_dirs: list[Path] = []
    for name in req.eval_fixtures:
        try:
            eval_dirs.append(resolve_fixture_dir(name))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    proposal = propose_retrain(
        ensemble_path=ensemble_path,
        eval_fixture_days=eval_dirs,
        brier_degrade=float(req.brier_degrade),
        min_labeled=int(req.min_labeled),
    )
    store.put("ml_retrain", proposal)
    return _safe_packet(proposal)


@router.post("/ml/retrain-apply")
def ml_retrain_apply(body: MlRetrainApplyRequest, request: Request) -> dict[str, Any]:
    """Apply retrain only with explicit confirm (Hermes/human gate).

    Refuses when confirm is false. Optionally requires last proposal status
    RETRAIN_SUGGESTED. Still advisory artifacts only — no capital/execution.
    """
    from hollersports.ml.pipeline import run_train_calibrate

    store = _store(request)
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm_required: set confirm=true after reviewing retrain-check",
        )
    if body.require_suggestion:
        last = store.get("ml_retrain")
        status = str((last or {}).get("status") or "") if isinstance(last, dict) else ""
        if status != "RETRAIN_SUGGESTED":
            raise HTTPException(
                status_code=400,
                detail=(
                    "retrain_not_suggested: run POST /v1/ml/retrain-check first "
                    f"(last status={status or 'EMPTY'}); or set require_suggestion=false"
                ),
            )

    train_dirs: list[Path] = []
    for name in body.train_fixtures:
        try:
            train_dirs.append(resolve_fixture_dir(name))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    out_dir = store.data_root / "ml"
    try:
        result = run_train_calibrate(
            train_dirs,
            None,
            out_dir=out_dir,
            prefer_sklearn=bool(body.prefer_sklearn),
            seed=int(body.seed),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    train_packet = {
        "schema_version": "HollerMlTrainPacket.v1",
        "status": "TRAINED",
        "source": "retrain_apply",
        **result,
        "train_fixtures": list(body.train_fixtures),
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "note": "human_or_hermes_confirmed_retrain",
    }
    ensemble_packet = {
        "ensemble_path": result["ensemble_path"],
        "ensemble_id": result.get("ensemble_id"),
        "model_id": result.get("model_id"),
        "data_hash": result.get("data_hash"),
        "metrics": result.get("metrics"),
        "capital_authority": False,
        "execution_authority": False,
    }
    store.put("ml_train", train_packet)
    store.put("ml_ensemble", ensemble_packet)
    store.put(
        "ml_retrain_apply",
        {
            "schema_version": "HollerMlRetrainApply.v1",
            "status": "APPLIED",
            "model_id": result.get("model_id"),
            "ensemble_path": result.get("ensemble_path"),
            "capital_authority": False,
            "execution_authority": False,
            "mode": "ADVISORY_ONLY",
        },
    )
    return _safe_packet(train_packet)


@router.post("/ml/train")
def ml_train(body: MlTrainRequest, request: Request) -> dict[str, Any]:
    """Train baseline + temperature ensemble from fixture days (offline advisory)."""
    from hollersports.ml.pipeline import run_train_calibrate

    store = _store(request)
    train_dirs: list[Path] = []
    for name in body.train_fixtures:
        try:
            train_dirs.append(resolve_fixture_dir(name))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    val_dirs: list[Path] | None = None
    if body.val_fixtures:
        val_dirs = []
        for name in body.val_fixtures:
            try:
                val_dirs.append(resolve_fixture_dir(name))
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    out_dir = store.data_root / "ml"
    try:
        result = run_train_calibrate(
            train_dirs,
            val_dirs,
            out_dir=out_dir,
            prefer_sklearn=bool(body.prefer_sklearn),
            seed=int(body.seed),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    train_packet = {
        "schema_version": "HollerMlTrainPacket.v1",
        "status": "TRAINED",
        **result,
        "train_fixtures": list(body.train_fixtures),
        "val_fixtures": list(body.val_fixtures or []),
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
    }
    ensemble_packet = {
        "ensemble_path": result["ensemble_path"],
        "ensemble_id": result.get("ensemble_id"),
        "model_id": result.get("model_id"),
        "data_hash": result.get("data_hash"),
        "metrics": result.get("metrics"),
        "capital_authority": False,
        "execution_authority": False,
    }
    store.put("ml_train", train_packet)
    store.put("ml_ensemble", ensemble_packet)
    return _safe_packet(train_packet)


@router.post("/ml/annotate")
def ml_annotate(body: MlAnnotateRequest, request: Request) -> dict[str, Any]:
    """Attach model_probability to last ingest markets from ensemble (fail closed).

    Does not invent probabilities when ensemble is missing (HTTP 404).
    Optional auto_compete reuses compete calibration gates.
    """
    store = _store(request)
    try:
        ensemble_path = _resolve_ensemble_path(store, body.ensemble_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ingest = store.get("ingest")
    if not isinstance(ingest, dict) or ingest.get("status") != "INGESTED":
        raise HTTPException(
            status_code=400,
            detail="no INGESTED run; POST /v1/runs/ingest or /runs/full-day first",
        )

    updated, n_scored = _annotate_ingest_markets(
        ingest, ensemble_path, ev_threshold=float(body.ev_threshold)
    )
    if n_scored == 0:
        raise HTTPException(
            status_code=400,
            detail="no markets could be scored (missing prices/features)",
        )

    # Keep multi-ingest slate in sync when present
    ingests = _stored_ingests(store)
    annotated_ingests: list[dict[str, Any]] = []
    if len(ingests) > 1:
        total_scored = 0
        for packet in ingests:
            if not isinstance(packet, dict):
                continue
            ann, n = _annotate_ingest_markets(
                packet, ensemble_path, ev_threshold=float(body.ev_threshold)
            )
            annotated_ingests.append(ann)
            total_scored += n
        n_scored = total_scored
        store.put("ingests", annotated_ingests)
        # Primary ingest: prefer same run_id match
        primary = next(
            (p for p in annotated_ingests if p.get("run_id") == updated.get("run_id")),
            annotated_ingests[0],
        )
        updated = primary
    else:
        annotated_ingests = [updated]
    store.put("ingest", updated)

    competition = None
    if body.auto_compete:
        calibration: dict[str, Any] | None = None
        allow = bool(body.allow_forecast_weighting)
        if body.use_auto_calibration:
            cal_packet = evaluate_calibration(
                _settlement_entries(store),
                allow_forecast_weighting=allow,
            )
            store.put("calibration", cal_packet)
            calibration = calibration_gate_from_packet(cal_packet)
        else:
            calibration = {
                "allow_forecast_weighting": allow,
                "reliability_status": str(body.reliability_status or "UNRELIABLE"),
            }
            store.put("calibration", calibration)
        # Multi-event free-first slates: compete the full annotated list (parity with /runs/compete).
        if len(annotated_ingests) > 1:
            competition = run_strategy_competition_multi(
                annotated_ingests,
                calibration=calibration,
                run_id=str(updated.get("run_id") or "") or None,
            )
        else:
            competition = run_strategy_competition(
                updated, calibration=calibration
            )
        store.put("competition", competition)

    _rebuild_dashboard(store)

    model_cands = []
    if isinstance(competition, dict):
        model_cands = [
            c
            for c in (competition.get("candidates") or [])
            if isinstance(c, dict)
            and c.get("strategy_id") == "MODEL_PROBABILITY_EDGE"
        ]

    edges = [
        float(m.get("model_edge") or 0)
        for m in (updated.get("markets") or [])
        if isinstance(m, dict) and m.get("model_edge") is not None
    ]
    annotate_packet = {
        "schema_version": "HollerMlAnnotatePacket.v1",
        "status": "ANNOTATED",
        "ensemble_path": str(ensemble_path),
        "annotated_markets": n_scored,
        "run_id": updated.get("run_id"),
        "event_id": updated.get("event_id"),
        "ev_threshold": float(body.ev_threshold),
        "ev_positive": sum(
            1
            for m in (updated.get("markets") or [])
            if isinstance(m, dict) and m.get("ev_meets_threshold")
        ),
        "max_model_edge": max(edges) if edges else None,
        "auto_compete": bool(body.auto_compete),
        "model_edge_enabled": (
            competition.get("model_edge_enabled") if isinstance(competition, dict) else None
        ),
        "model_edge_candidate_count": len(model_cands),
        "competition_status": (
            competition.get("status") if isinstance(competition, dict) else None
        ),
        "authority": "SHADOW_ONLY",
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "note": "advisory_ml_annotate_no_money",
    }
    store.put("ml_annotate", annotate_packet)
    return _safe_packet(annotate_packet)
