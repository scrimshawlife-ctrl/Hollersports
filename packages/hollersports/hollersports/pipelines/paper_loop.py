"""Paper loop: candidates → execution guard → portfolio simulate → ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.paper.ledger import append_paper_entry
from hollersports.paper.store import ledger_path as default_ledger_path
from hollersports.runes.execution_guard import run_execution_guard
from hollersports.runes.portfolio_simulator import simulate_paper_entry


def run_paper_loop(
    candidates: Sequence[Mapping[str, Any] | dict[str, Any]] | None,
    context: Mapping[str, Any] | dict[str, Any] | None,
) -> dict[str, Any]:
    """Run paper execution for a list of strategy candidates.

    For each candidate:
      1. run_execution_guard
      2. if APPROVED_FOR_PAPER → simulate_paper_entry + append_paper_entry

    Returns a summary packet with executions, portfolio entries, and counts.
    Never grants capital or execution authority.
    """
    ctx: dict[str, Any] = dict(context) if isinstance(context, Mapping) else {}
    run_id = str(ctx.get("run_id") or "UNKNOWN")
    cand_list: list[Mapping[str, Any]] = (
        [c for c in candidates if isinstance(c, Mapping)] if candidates else []
    )

    ledger_file: Path
    if ctx.get("ledger_path"):
        ledger_file = Path(str(ctx["ledger_path"]))
    else:
        portfolio_id = str(ctx.get("portfolio_id") or "default")
        ledger_file = default_ledger_path(f"{portfolio_id}.jsonl")

    executions: list[dict[str, Any]] = []
    portfolio_entries: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    approved = 0
    rejected = 0

    for cand in cand_list:
        execution = run_execution_guard(cand, ctx)
        executions.append(execution)

        if execution.get("status") == "APPROVED_FOR_PAPER":
            approved += 1
            portfolio = simulate_paper_entry(execution, ctx)
            portfolio_entries.append(portfolio)
            if portfolio.get("status") == "RECORDED":
                prov = execution.get("provenance") if isinstance(
                    execution.get("provenance"), Mapping
                ) else {}
                strategy_id = str(
                    cand.get("strategy_id")
                    or (prov or {}).get("strategy_id")
                    or ""
                )
                ledger_entry = {
                    "entry_id": portfolio.get("entry_id"),
                    "run_id": portfolio.get("run_id"),
                    "portfolio_id": portfolio.get("portfolio_id"),
                    "event_id": portfolio.get("event_id"),
                    "market_id": portfolio.get("market_id"),
                    "selection": portfolio.get("selection"),
                    "price": portfolio.get("price"),
                    "stake": portfolio.get("paper_stake"),
                    "paper_result": portfolio.get("paper_result"),
                    "expected_value": portfolio.get("expected_value"),
                    "packet_refs": portfolio.get("packet_refs") or {},
                    "status": portfolio.get("status"),
                    "strategy_id": strategy_id,
                    "league": str(cand.get("league") or ""),
                    "market_type": str(cand.get("market_type") or ""),
                }
                recorded = append_paper_entry(ledger_file, ledger_entry)
                ledger_rows.append(recorded)
        else:
            rejected += 1

    out: dict[str, Any] = {
        "schema_version": "PaperLoopPacket.v1",
        "status": "COMPUTED",
        "run_id": run_id,
        "candidate_count": len(cand_list),
        "approved_count": approved,
        "rejected_count": rejected,
        "executions": executions,
        "portfolio_entries": portfolio_entries,
        "ledger_entries": ledger_rows,
        "ledger_path": str(ledger_file),
        "authority": Authority.SHADOW_FIRST.value,
        "capital_authority": False,
        "execution_authority": False,
        "provenance": {
            "mode": "PAPER_ONLY",
        },
    }
    assert_no_live_capital(out)
    return out
