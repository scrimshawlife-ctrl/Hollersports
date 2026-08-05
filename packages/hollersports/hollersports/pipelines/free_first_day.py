"""Headless free-first operator day: observe → compete → paper → settle → bank.

Advisory only — no real money, no book placement. Prefer fixtures for CI;
use injected ESPN/odds raw offline. Live fetch is opt-in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.governance.authority import assert_no_live_capital
from hollersports.paper.settlement_history import (
    append_settlement_history,
    calibration_entries_for_store,
)
from hollersports.pipelines.paper_loop import run_paper_loop
from hollersports.pipelines.strategy_competition import run_strategy_competition_multi
from hollersports.runes.calibration_evaluator import evaluate_calibration
from hollersports.runes.settlement_engine import settle_entry
from hollersports.sources.espn_outcomes import (
    merge_espn_moneyline_results,
    normalize_espn_moneyline_results,
)
from hollersports.sources.espn_scoreboard import ESPN_LEAGUE_PATHS, fetch_espn_scoreboard
from hollersports.sources.free_first_ingest import build_live_observation_pack


_FIXTURE_GATES: dict[str, bool] = {
    "source_health_gate": True,
    "governance_gate": True,
    "truth_gate": True,
    "liquidity_gate": True,
    "bankroll_gate": True,
}


def _market_prices(ingests: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for ing in ingests:
        if not isinstance(ing, Mapping):
            continue
        for m in ing.get("markets") or []:
            if not isinstance(m, Mapping):
                continue
            mid = str(m.get("market_id") or "")
            if mid and m.get("price") is not None:
                try:
                    prices.setdefault(mid, float(m["price"]))
                except (TypeError, ValueError):
                    continue
    return prices


def _top_candidates(
    candidates: Sequence[Mapping[str, Any]],
    n: int,
    prices: Mapping[str, float],
) -> list[dict[str, Any]]:
    ranked = sorted(
        [dict(c) for c in candidates if isinstance(c, Mapping)],
        key=lambda c: float(c.get("score") or 0.0),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for c in ranked[: max(0, n)]:
        mid = str(c.get("market_id") or "")
        if c.get("price") is None and mid in prices:
            c["price"] = prices[mid]
        out.append(c)
    return out


def _index_results(results: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for r in results:
        if not isinstance(r, Mapping):
            continue
        row = dict(r)
        eid = str(row.get("event_id") or "")
        mid = str(row.get("market_id") or "")
        sel = str(row.get("selection") or "")
        if mid:
            index[(eid, mid)] = row
            index[("", mid)] = row
        if eid and sel:
            index[(eid, f"sel:{sel}")] = row
            index[(eid, f"sel:{sel.upper()}")] = row
    return index


def _expand_via_joins(
    results: list[dict[str, Any]],
    ingests: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    alias: dict[str, set[str]] = {}
    for ing in ingests:
        if not isinstance(ing, Mapping):
            continue
        refs = ing.get("source_refs") if isinstance(ing.get("source_refs"), Mapping) else {}
        join = refs.get("join") if isinstance(refs.get("join"), Mapping) else {}
        left = str(join.get("left_event_id") or "")
        right = str(join.get("right_event_id") or "")
        top = str(ing.get("event_id") or "")
        for a, b in ((left, right), (right, left), (left, top)):
            if a and b and a != b:
                alias.setdefault(a, set()).add(b)
    if not alias:
        return results
    expanded = list(results)
    for row in results:
        eid = str(row.get("event_id") or "")
        for alt in alias.get(eid, ()):
            copy = dict(row)
            copy["event_id"] = alt
            expanded.append(copy)
    return expanded


def _lookup(
    index: dict[tuple[str, str], dict[str, Any]],
    event_id: str,
    market_id: str,
    selection: str,
) -> dict[str, Any] | None:
    eid, mid, sel = str(event_id or ""), str(market_id or ""), str(selection or "")
    if (eid, mid) in index:
        return index[(eid, mid)]
    if mid and ("", mid) in index:
        return index[("", mid)]
    if eid and sel:
        for key in ((eid, f"sel:{sel}"), (eid, f"sel:{sel.upper()}")):
            if key in index:
                return index[key]
    return None


def run_free_first_operator_day(
    *,
    data_root: Path | str,
    run_id: str | None = None,
    leagues: Sequence[str] | None = None,
    espn_raw: dict[str, Any] | None = None,
    odds_raw: list[dict[str, Any]] | None = None,
    settle_espn_raw: dict[str, Any] | None = None,
    fetch_espn: bool = True,
    fetch_odds: bool = True,
    fetch_espn_finals: bool = False,
    paper_top_n: int = 20,
    bankroll: float = 1000.0,
    human_max_stake: float = 25.0,
) -> dict[str, Any]:
    """Closed free-first day into the calibration bank (advisory simulation).

    Settlement uses injected ``settle_espn_raw`` when provided; otherwise optional
    live ``fetch_espn_finals``. Missing/non-final outcomes stay PENDING and are
    collapsed out of calibration until a later terminal re-settle.
    """
    root = Path(data_root)
    root.mkdir(parents=True, exist_ok=True)
    ledgers = root / "ledgers"
    ledgers.mkdir(parents=True, exist_ok=True)

    pack = build_live_observation_pack(
        run_id=run_id,
        fetch_espn=fetch_espn,
        fetch_odds=fetch_odds,
        espn_raw=espn_raw,
        odds_raw=odds_raw,
        leagues=leagues,
    )
    assert_no_live_capital(pack)
    ingests = [i for i in (pack.get("ingests") or []) if isinstance(i, dict)]
    rid = str(pack.get("run_id") or run_id or "FREE-FIRST")

    competition = run_strategy_competition_multi(ingests, run_id=rid)
    assert_no_live_capital(competition)

    prices = _market_prices(ingests)
    cand_list = [
        c
        for c in (competition.get("candidates") or [])
        if isinstance(c, Mapping) and c.get("status") == "CANDIDATE"
    ]
    paper_candidates = _top_candidates(cand_list, paper_top_n, prices)
    paper = run_paper_loop(
        paper_candidates,
        {
            "run_id": rid,
            "portfolio_id": "free-first",
            "bankroll": bankroll,
            "human_max_stake": human_max_stake,
            "gates": dict(_FIXTURE_GATES),
            "ledger_path": ledgers / "free_first_paper.jsonl",
        },
    )
    assert_no_live_capital(paper)

    result_errors: list[str] = []
    results_rows: list[dict[str, Any]] = []
    if settle_espn_raw is not None:
        lg = list(leagues) if leagues else ["NBA"]
        for league in lg:
            try:
                results_rows.extend(
                    normalize_espn_moneyline_results(settle_espn_raw, league=str(league))
                )
            except Exception as exc:  # noqa: BLE001
                result_errors.append(f"settle_raw:{league}:{type(exc).__name__}:{exc}")
    elif fetch_espn_finals:
        lg = list(leagues) if leagues else list(ESPN_LEAGUE_PATHS.keys())
        packs: list[tuple[dict[str, Any], str]] = []
        for league in lg:
            try:
                packs.append((fetch_espn_scoreboard(league=str(league)), str(league)))
            except Exception as exc:  # noqa: BLE001
                result_errors.append(f"espn_fetch:{league}:{type(exc).__name__}:{exc}")
        results_rows = merge_espn_moneyline_results(packs)

    results_rows = _expand_via_joins(results_rows, ingests)
    index = _index_results(results_rows)

    settlement_entries: list[dict[str, Any]] = []
    for entry in paper.get("ledger_entries") or paper.get("portfolio_entries") or []:
        if not isinstance(entry, Mapping):
            continue
        settle_input = dict(entry)
        if "stake" not in settle_input and "paper_stake" in settle_input:
            settle_input["stake"] = settle_input["paper_stake"]
        result = _lookup(
            index,
            str(entry.get("event_id") or ""),
            str(entry.get("market_id") or ""),
            str(entry.get("selection") or ""),
        )
        settlement_entries.append(settle_entry(settle_input, result))

    written = append_settlement_history(
        root,
        settlement_entries,
        run_id=rid,
        fixture="free-first",
    )
    cal_entries = calibration_entries_for_store(root, settlement_entries)
    calibration = evaluate_calibration(cal_entries, allow_forecast_weighting=True)

    out = {
        "schema_version": "FreeFirstOperatorDay.v1",
        "status": pack.get("status"),
        "run_id": rid,
        "ingest_count": len(ingests),
        "competed_event_count": competition.get("competed_event_count"),
        "candidate_count": competition.get("candidate_count"),
        "paper_status": paper.get("status"),
        "paper_approved": paper.get("approved_count"),
        "settlement_count": len(settlement_entries),
        "bank_written": len(written),
        "result_count": len(results_rows),
        "result_errors": result_errors,
        "calibration": {
            "status": calibration.get("status"),
            "sample_size": calibration.get("sample_size"),
            "model_edge_allowed": calibration.get("model_edge_allowed"),
        },
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "errors": list(pack.get("errors") or []),
    }
    assert_no_live_capital(out)
    return out
