"""Advice-quality reliability buckets by strategy / league / market (no money)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.schemas.hashing import packet_hash

_SETTLED = frozenset({"WIN", "LOSS", "PUSH", "VOID"})


def _bucket_key(entry: Mapping[str, Any], dimension: str) -> str:
    if dimension == "strategy_id":
        return str(entry.get("strategy_id") or "UNKNOWN")
    if dimension == "league":
        return str(entry.get("league") or "UNKNOWN")
    if dimension == "market_type":
        return str(entry.get("market_type") or "UNKNOWN")
    return "ALL"


def compute_reliability_buckets(
    settled_entries: Sequence[Mapping[str, Any]] | None,
    *,
    dimensions: Sequence[str] = ("strategy_id", "league", "market_type"),
    min_sample: int = 1,
) -> dict[str, Any]:
    """Bucket settled paper outcomes for advice calibration.

    PENDING excluded. ROI/hit_rate are simulation metrics only — not real P&L.
    """
    rows = [
        dict(e)
        for e in (settled_entries or [])
        if isinstance(e, Mapping) and str(e.get("status") or "").upper() in _SETTLED
    ]

    buckets: list[dict[str, Any]] = []
    for dim in dimensions:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in rows:
            groups[_bucket_key(e, dim)].append(e)
        for key, group in sorted(groups.items()):
            n = len(group)
            if n < min_sample:
                continue
            wins = sum(1 for g in group if str(g.get("status")).upper() == "WIN")
            stakes = [float(g.get("stake") or g.get("paper_stake") or 0.0) for g in group]
            pnls = [float(g.get("pnl") or g.get("settled_value") or 0.0) for g in group]
            stake_sum = sum(stakes) or 0.0
            pnl_sum = sum(pnls)
            buckets.append(
                {
                    "dimension": dim,
                    "key": key,
                    "sample_size": n,
                    "hit_rate": round(wins / n, 4) if n else 0.0,
                    "sim_roi": round(pnl_sum / stake_sum, 4) if stake_sum else 0.0,
                    "note": "simulation_metrics_only",
                }
            )

    packet = {
        "schema_version": "ReliabilityBucketPacket.v1",
        "status": "COMPUTED" if rows else "EMPTY",
        "sample_size": len(rows),
        "bucket_count": len(buckets),
        "buckets": buckets,
        "authority": Authority.SHADOW_ONLY.value,
        "capital_authority": False,
        "execution_authority": False,
        "mode": "ADVISORY_ONLY",
        "provenance": {
            "excluded_pending": True,
            "purpose": "advice_quality_calibration",
            "real_money": False,
        },
    }
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k != "packet_hash"}
    )
    assert_no_live_capital(packet)
    return packet
