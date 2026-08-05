"""Settlement engine: map paper entries + results → SettlementPacket.v1."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.schemas.packets import SettlementPacket

_TERMINAL = frozenset({"WIN", "LOSS", "PUSH", "VOID"})


def _to_decimal_price(price: float) -> float:
    """Normalize American or decimal odds to decimal multiplier."""
    p = float(price)
    if p == 0:
        return 0.0
    # American odds: negative favorites or positive dogs beyond decimal range.
    if p <= -100:
        return 1.0 + (100.0 / abs(p))
    if p >= 100:
        return 1.0 + (p / 100.0)
    # Already decimal (e.g. 1.91) or fractional-like positive < 100.
    return p


def _compute_pnl(status: str, stake: float, price: float) -> float:
    stake_f = float(stake)
    if status == "WIN":
        dec = _to_decimal_price(price)
        if dec <= 0:
            return 0.0
        return stake_f * (dec - 1.0)
    if status == "LOSS":
        return -stake_f
    # PUSH, VOID, PENDING, NOT_COMPUTABLE
    return 0.0


def settle_entry(
    entry: Mapping[str, Any] | dict[str, Any] | None,
    result: Mapping[str, Any] | dict[str, Any] | None,
) -> dict[str, Any]:
    """Settle a paper portfolio entry against an optional market result.

    - result is None or missing outcome → PENDING
    - known terminal result → WIN/LOSS/PUSH/VOID with pnl
    Always SHADOW_ONLY; never grants capital or execution authority.
    """
    ent: Mapping[str, Any] = entry if isinstance(entry, Mapping) else {}
    entry_id = str(ent.get("entry_id") or "")
    run_id = str(ent.get("run_id") or "")
    portfolio_id = str(ent.get("portfolio_id") or "")
    event_id = str(ent.get("event_id") or "")
    market_id = str(ent.get("market_id") or "")
    selection = str(ent.get("selection") or "")
    stake = float(ent.get("stake") or ent.get("paper_stake") or 0.0)
    price = float(ent.get("price") or 0.0)

    if result is None or not isinstance(result, Mapping):
        packet = SettlementPacket(
            status="PENDING",
            entry_id=entry_id,
            run_id=run_id,
            portfolio_id=portfolio_id,
            event_id=event_id,
            market_id=market_id,
            selection=selection,
            stake=stake,
            price=price,
            pnl=0.0,
            final_score=None,
            result_source="",
            settled_at="",
            authority=Authority.SHADOW_ONLY.value,
            capital_authority=False,
            execution_authority=False,
            reason="result_missing",
            provenance={"source": None},
        )
        out = packet.model_dump()
        assert_no_live_capital(out)
        return out

    raw_status = str(result.get("result") or result.get("status") or "").upper()
    source = str(result.get("source") or result.get("result_source") or "")
    final_score = result.get("final_score")
    final_score_s = str(final_score) if final_score is not None else None
    settled_at = str(result.get("settled_at") or "")

    if raw_status not in _TERMINAL:
        packet = SettlementPacket(
            status="PENDING",
            entry_id=entry_id,
            run_id=run_id,
            portfolio_id=portfolio_id,
            event_id=event_id,
            market_id=market_id,
            selection=selection,
            stake=stake,
            price=price,
            pnl=0.0,
            final_score=final_score_s,
            result_source=source,
            settled_at=settled_at,
            authority=Authority.SHADOW_ONLY.value,
            capital_authority=False,
            execution_authority=False,
            reason="result_unresolved",
            provenance={"source": source or None},
        )
        out = packet.model_dump()
        assert_no_live_capital(out)
        return out

    pnl = _compute_pnl(raw_status, stake, price)
    strategy_id = str(ent.get("strategy_id") or "")
    league = str(ent.get("league") or "")
    market_type = str(ent.get("market_type") or "")
    packet = SettlementPacket(
        status=raw_status,  # type: ignore[arg-type]
        entry_id=entry_id,
        run_id=run_id,
        portfolio_id=portfolio_id,
        event_id=event_id,
        market_id=market_id,
        selection=selection,
        stake=stake,
        price=price,
        pnl=float(pnl),
        final_score=final_score_s,
        result_source=source,
        settled_at=settled_at,
        authority=Authority.SHADOW_ONLY.value,
        capital_authority=False,
        execution_authority=False,
        provenance={
            "source": source or None,
            "result": raw_status,
            "strategy_id": strategy_id or None,
        },
    )
    out = packet.model_dump()
    # Extra dims for reliability / calibration bank (schema allows extra).
    if strategy_id:
        out["strategy_id"] = strategy_id
    if league:
        out["league"] = league
    if market_type:
        out["market_type"] = market_type
    assert_no_live_capital(out)
    return out
