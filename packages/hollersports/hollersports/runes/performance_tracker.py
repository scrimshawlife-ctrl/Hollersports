"""Performance tracker: settled paper entries → PerformancePacket.v1."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.schemas.packets import PerformancePacket

_SETTLED = frozenset({"WIN", "LOSS", "PUSH", "VOID"})


def compute_performance(
    settled_entries: Sequence[Mapping[str, Any] | dict[str, Any]] | None,
) -> dict[str, Any]:
    """Compute portfolio performance metrics excluding PENDING entries.

    Always SHADOW_ONLY; never grants capital or execution authority.
    """
    rows = [
        dict(e)
        for e in (settled_entries or [])
        if isinstance(e, Mapping) and str(e.get("status") or "").upper() in _SETTLED
    ]
    sample_size = len(rows)
    portfolio_id = ""
    for e in rows:
        if e.get("portfolio_id"):
            portfolio_id = str(e["portfolio_id"])
            break

    if sample_size == 0:
        packet = PerformancePacket(
            status="INFERRED",
            portfolio_id=portfolio_id,
            sample_size=0,
            roi=0.0,
            hit_rate=0.0,
            clv_retention=0.0,
            max_drawdown=0.0,
            authority=Authority.SHADOW_ONLY.value,
            capital_authority=False,
            execution_authority=False,
            reason="no_settled_entries",
            provenance={"excluded_pending": True},
        )
        out = packet.model_dump()
        assert_no_live_capital(out)
        return out

    total_stake = sum(float(e.get("stake") or e.get("paper_stake") or 0.0) for e in rows)
    total_pnl = sum(float(e.get("pnl") or 0.0) for e in rows)
    wins = sum(1 for e in rows if str(e.get("status")).upper() == "WIN")
    hit_rate = wins / sample_size if sample_size else 0.0
    roi = (total_pnl / total_stake) if total_stake > 0 else 0.0

    # Simple equity-curve max drawdown on sequential pnl (fraction of peak equity).
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for e in rows:
        equity += float(e.get("pnl") or 0.0)
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        elif equity < 0 and peak == 0:
            # Drawdown from zero bankroll baseline using abs cumulative loss vs stake.
            if total_stake > 0:
                max_dd = max(max_dd, min(1.0, abs(equity) / total_stake))

    clv_vals = [
        float(e["clv_retention"])
        for e in rows
        if e.get("clv_retention") is not None
    ]
    clv_retention = sum(clv_vals) / len(clv_vals) if clv_vals else 0.0

    average_stake = total_stake / sample_size
    average_settled_value = total_pnl / sample_size

    packet = PerformancePacket(
        status="INFERRED",
        portfolio_id=portfolio_id,
        sample_size=float(sample_size),
        roi=float(roi),
        hit_rate=float(hit_rate),
        clv_retention=float(clv_retention),
        max_drawdown=float(max(0.0, min(1.0, max_dd))),
        average_stake=float(average_stake),
        average_settled_value=float(average_settled_value),
        authority=Authority.SHADOW_ONLY.value,
        capital_authority=False,
        execution_authority=False,
        provenance={
            "excluded_pending": True,
            "total_stake": total_stake,
            "total_pnl": total_pnl,
        },
    )
    out = packet.model_dump()
    assert_no_live_capital(out)
    return out
