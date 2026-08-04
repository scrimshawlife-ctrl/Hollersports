"""Operator dashboard projection: state → OperatorDashboardPacket.v1.

Projection-only read model. Never mutates ledger or grants capital.
"""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.schemas.packets import OperatorDashboardPacket


def project_dashboard(state: Mapping[str, Any] | dict[str, Any] | None) -> dict[str, Any]:
    """Project operator dashboard panels from run state.

    Always authority PROJECTION_ONLY with capital/execution false.
    Never includes live mode or place-bet controls.
    """
    st: Mapping[str, Any] = state if isinstance(state, Mapping) else {}

    run_id = str(st.get("run_id") or "UNKNOWN")
    portfolio_id = str(st.get("portfolio_id") or "default")

    paper = st.get("paper") if isinstance(st.get("paper"), Mapping) else {}
    settlements = st.get("settlements")
    performance = st.get("performance") if isinstance(st.get("performance"), Mapping) else {}
    promotion = st.get("promotion") if isinstance(st.get("promotion"), Mapping) else {}
    ingest = st.get("ingest") if isinstance(st.get("ingest"), Mapping) else {}
    sources = st.get("sources")
    if not isinstance(sources, Mapping):
        sources = {
            "source_id": ingest.get("source_id") or "FIXTURE",
            "source_health": ingest.get("source_health") or {},
            "status": ingest.get("status"),
        }

    settlement_list: list[Any]
    if isinstance(settlements, Mapping) and "entries" in settlements:
        settlement_list = list(settlements.get("entries") or [])
    elif isinstance(settlements, list):
        settlement_list = settlements
    else:
        settlement_list = []

    pending = sum(
        1
        for s in settlement_list
        if isinstance(s, Mapping) and str(s.get("status") or "").upper() == "PENDING"
    )
    settled = sum(
        1
        for s in settlement_list
        if isinstance(s, Mapping)
        and str(s.get("status") or "").upper() in {"WIN", "LOSS", "PUSH", "VOID"}
    )

    failed_gates = list(promotion.get("failed_gates") or [])

    panels: dict[str, Any] = {
        "paper_portfolio_summary": {
            "approved_count": paper.get("approved_count", 0),
            "rejected_count": paper.get("rejected_count", 0),
            "candidate_count": paper.get("candidate_count", 0),
            "ledger_path": paper.get("ledger_path"),
            "status": paper.get("status"),
        },
        "settlement_queue": {
            "total": len(settlement_list),
            "pending": pending,
            "settled": settled,
            "entries": settlement_list,
        },
        "performance_metrics": dict(performance),
        "promotion_gate_status": {
            "status": promotion.get("status"),
            "passed_gates": list(promotion.get("passed_gates") or []),
            "failed_gates": failed_gates,
            "target_id": promotion.get("target_id"),
        },
        "failed_gates": failed_gates,
        "sources": dict(sources),
    }

    packet = OperatorDashboardPacket(
        status="PROJECTED",
        run_id=run_id,
        portfolio_id=portfolio_id,
        panels=panels,
        authority=Authority.PROJECTION_ONLY.value,
        capital_authority=False,
        execution_authority=False,
        provenance={
            "mode": "PROJECTION_ONLY",
            "live_mode": False,
        },
    )
    out = packet.model_dump()
    # Hard invariant: never surface live betting UX.
    out.pop("mode", None)
    if out.get("mode") == "LIVE_APPROVED":
        out["mode"] = "PROJECTION_ONLY"
    assert out["authority"] == Authority.PROJECTION_ONLY.value
    assert out["capital_authority"] is False
    assert out["execution_authority"] is False
    assert_no_live_capital(out)
    return out
