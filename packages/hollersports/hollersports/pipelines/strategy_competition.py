"""Strategy competition loop: ingest packet → sorted shadow-only candidates."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.governance.fail_closed import not_computable
from hollersports.governance.gates import calibration_allows_model_edge
from hollersports.strategies.registry import load_strategies


def _sort_key(candidate: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(candidate.get("strategy_id") or ""),
        str(candidate.get("market_id") or ""),
        str(candidate.get("selection") or ""),
    )


def run_strategy_competition(
    packet: dict[str, Any] | Mapping[str, Any] | None,
    *,
    calibration: dict[str, Any] | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run registered strategies against an ingested market packet.

    - Only status INGESTED is computable.
    - Model edge loaded only when calibration_allows_model_edge(calibration).
    - Candidates sorted by (strategy_id, market_id, selection).
    - All candidates remain SHADOW_ONLY with capital/execution false.
    """
    if not isinstance(packet, Mapping) or packet.get("status") != "INGESTED":
        reason = "ingest_not_ingested"
        if isinstance(packet, Mapping):
            status = packet.get("status")
            if status == "REJECTED":
                reason = "ingest_rejected"
            elif status == "NOT_COMPUTABLE":
                reason = "ingest_not_computable"
            elif status is None:
                reason = "ingest_missing_status"
        else:
            reason = "invalid_ingest_packet"
        out = not_computable(
            "StrategyCompetitionPacket.v1",
            reason,
            run_id=str(packet.get("run_id") or "UNKNOWN")
            if isinstance(packet, Mapping)
            else "UNKNOWN",
            event_id=str(packet.get("event_id") or "UNKNOWN")
            if isinstance(packet, Mapping)
            else "UNKNOWN",
            candidates=[],
            candidate_count=0,
        )
        assert_no_live_capital(out)
        return out

    allow_model = calibration_allows_model_edge(calibration)
    strategies = load_strategies(allow_model_edge=allow_model)

    candidates: list[dict[str, Any]] = []
    for strategy in strategies:
        generated = strategy.generate(packet)
        for c in generated:
            # Enforce shadow-only even if a strategy misbehaves.
            c = dict(c)
            c["authority"] = Authority.SHADOW_ONLY.value
            c["capital_authority"] = False
            c["execution_authority"] = False
            candidates.append(c)

    candidates.sort(key=_sort_key)

    out: dict[str, Any] = {
        "schema_version": "StrategyCompetitionPacket.v1",
        "status": "COMPUTED",
        "run_id": str(packet.get("run_id") or "UNKNOWN"),
        "event_id": str(packet.get("event_id") or "UNKNOWN"),
        "candidates": candidates,
        "candidate_count": len(candidates),
        "authority": Authority.SHADOW_ONLY.value,
        "capital_authority": False,
        "execution_authority": False,
        "model_edge_enabled": allow_model,
        "provenance": {
            "strategy_ids": [s.strategy_id for s in strategies],
        },
    }
    assert_no_live_capital(out)
    return out
