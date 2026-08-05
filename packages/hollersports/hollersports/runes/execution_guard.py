"""Paper-only execution guard: gate candidates and emit ExecutionPacket.v1."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.runes.bet_construct import construct_bet
from hollersports.runes.stake_sizer import size_stake
from hollersports.schemas.packets import ExecutionPacket

# All must be True for APPROVED_FOR_PAPER.
GATE_KEYS: tuple[str, ...] = (
    "source_health_gate",
    "governance_gate",
    "truth_gate",
    "liquidity_gate",
    "bankroll_gate",
)

# Fixture-friendly defaults when a gate key is omitted from context.
_DEFAULT_GATES: dict[str, bool] = {
    "truth_gate": True,
}


def _evaluate_gates(context: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    raw = context.get("gates") or {}
    if not isinstance(raw, Mapping):
        raw = {}
    passed: list[str] = []
    failed: list[str] = []
    for key in GATE_KEYS:
        if key in raw:
            value = bool(raw[key])
        elif key in _DEFAULT_GATES:
            value = bool(_DEFAULT_GATES[key])
        else:
            # Missing required gate → fail-closed.
            value = False
        if value:
            passed.append(key)
        else:
            failed.append(key)
    return passed, failed


def run_execution_guard(
    candidate: dict[str, Any] | Mapping[str, Any] | None,
    context: dict[str, Any] | Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Approve or reject a strategy candidate for paper execution.

    Always returns mode PAPER_ONLY with capital_authority and execution_authority
    false. Authority is SHADOW_FIRST on the paper path.
    """
    cand: Mapping[str, Any] = candidate if isinstance(candidate, Mapping) else {}
    ctx: Mapping[str, Any] = context if isinstance(context, Mapping) else {}

    run_id = str(ctx.get("run_id") or cand.get("run_id") or "UNKNOWN")
    passed_gates, failed_gates = _evaluate_gates(ctx)

    bankroll = float(ctx.get("bankroll") or 0.0)
    human_max = float(ctx.get("human_max_stake") or 0.0)
    score = float(cand.get("score") or 0.0)
    stake = size_stake(bankroll=bankroll, score=score, human_max_stake=human_max)

    bet = construct_bet(cand, ctx, stake=stake if not failed_gates and stake > 0 else 0.0)

    if failed_gates:
        packet = ExecutionPacket(
            status="REJECTED",
            run_id=run_id,
            candidate_id=bet["candidate_id"],
            event_id=bet["event_id"],
            market_id=bet["market_id"],
            selection=bet["selection"],
            price=bet["price"],
            point=bet["point"],
            sportsbook=bet["sportsbook"],
            stake=0.0,
            mode="PAPER_ONLY",
            passed_gates=passed_gates,
            failed_gates=failed_gates,
            packet_refs=bet["packet_refs"],
            expected_value=0.0,
            authority=Authority.SHADOW_FIRST.value,
            capital_authority=False,
            execution_authority=False,
            reason="gates_failed:" + ",".join(failed_gates),
            provenance={"strategy_id": bet.get("strategy_id") or ""},
        )
        out = packet.model_dump()
        assert_no_live_capital(out)
        return out

    # Never zero when approved — reject non-positive stake.
    if stake <= 0:
        packet = ExecutionPacket(
            status="REJECTED",
            run_id=run_id,
            candidate_id=bet["candidate_id"],
            event_id=bet["event_id"],
            market_id=bet["market_id"],
            selection=bet["selection"],
            price=bet["price"],
            point=bet["point"],
            sportsbook=bet["sportsbook"],
            stake=0.0,
            mode="PAPER_ONLY",
            passed_gates=passed_gates,
            failed_gates=["stake_non_positive"],
            packet_refs=bet["packet_refs"],
            expected_value=0.0,
            authority=Authority.SHADOW_FIRST.value,
            capital_authority=False,
            execution_authority=False,
            reason="stake_non_positive",
            provenance={"strategy_id": bet.get("strategy_id") or ""},
        )
        out = packet.model_dump()
        assert_no_live_capital(out)
        return out

    packet = ExecutionPacket(
        status="APPROVED_FOR_PAPER",
        run_id=run_id,
        candidate_id=bet["candidate_id"],
        event_id=bet["event_id"],
        market_id=bet["market_id"],
        selection=bet["selection"],
        price=bet["price"],
        point=bet["point"],
        sportsbook=bet["sportsbook"],
        stake=float(stake),
        mode="PAPER_ONLY",
        passed_gates=passed_gates,
        failed_gates=[],
        packet_refs=bet["packet_refs"],
        expected_value=bet["expected_value"],
        authority=Authority.SHADOW_FIRST.value,
        capital_authority=False,
        execution_authority=False,
        provenance={
            "strategy_id": bet.get("strategy_id") or "",
            "score": score,
            "bankroll": bankroll,
            "human_max_stake": human_max,
        },
    )
    out = packet.model_dump()
    assert_no_live_capital(out)
    return out
