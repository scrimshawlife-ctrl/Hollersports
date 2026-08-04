"""Paper portfolio simulation: map approved execution → portfolio entry (no capital)."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.schemas.packets import PaperPortfolioPacket


def simulate_paper_entry(
    execution: Mapping[str, Any] | None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a PaperPortfolioPacket for an approved paper execution.

    Non-approved or invalid execution → NOT_COMPUTABLE. Always capital/execution false.
    """
    ctx: Mapping[str, Any] = context if isinstance(context, Mapping) else {}
    exe: Mapping[str, Any] = execution if isinstance(execution, Mapping) else {}

    run_id = str(exe.get("run_id") or ctx.get("run_id") or "UNKNOWN")
    portfolio_id = str(ctx.get("portfolio_id") or "default")
    starting_bankroll = float(ctx.get("bankroll") or ctx.get("starting_bankroll") or 0.0)

    if exe.get("status") != "APPROVED_FOR_PAPER":
        packet = PaperPortfolioPacket(
            status="NOT_COMPUTABLE",
            run_id=run_id,
            portfolio_id=portfolio_id,
            starting_bankroll=starting_bankroll,
            paper_stake=0.0,
            paper_result="NOT_COMPUTABLE",
            authority=Authority.SHADOW_ONLY.value,
            capital_authority=False,
            execution_authority=False,
            reason="execution_not_approved",
            provenance={},
        )
        out = packet.model_dump()
        assert_no_live_capital(out)
        return out

    entry_id = str(
        exe.get("entry_id")
        or ctx.get("entry_id")
        or f"paper:{run_id}:{exe.get('candidate_id') or 'unknown'}"
    )
    packet_refs = exe.get("packet_refs") or {}
    if not isinstance(packet_refs, Mapping):
        packet_refs = {}
    refs = dict(packet_refs)
    refs.setdefault("execution", exe.get("candidate_id") or run_id)

    packet = PaperPortfolioPacket(
        status="RECORDED",
        run_id=run_id,
        portfolio_id=portfolio_id,
        entry_id=entry_id,
        starting_bankroll=starting_bankroll,
        paper_stake=float(exe.get("stake") or 0.0),
        paper_result="PENDING",
        expected_value=float(exe.get("expected_value") or 0.0),
        settled_value=None,
        event_id=str(exe.get("event_id") or ""),
        market_id=str(exe.get("market_id") or ""),
        selection=str(exe.get("selection") or ""),
        price=float(exe.get("price") or 0.0),
        packet_refs=refs,
        authority=Authority.SHADOW_ONLY.value,
        capital_authority=False,
        execution_authority=False,
        provenance={
            "candidate_id": exe.get("candidate_id") or "",
            "mode": exe.get("mode") or "PAPER_ONLY",
        },
    )
    out = packet.model_dump()
    assert_no_live_capital(out)
    return out
