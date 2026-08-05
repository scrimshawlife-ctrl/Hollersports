"""Strategy competition loop: ingest packet → sorted shadow-only candidates."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

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


def _multi_sort_key(candidate: Mapping[str, Any]) -> tuple[float, str, str, str, str]:
    """Higher score first, then stable identity keys (incl. event)."""
    try:
        score = float(candidate.get("score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return (
        -score,
        str(candidate.get("strategy_id") or ""),
        str(candidate.get("market_id") or ""),
        str(candidate.get("selection") or ""),
        str(candidate.get("event_id") or ""),
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


def run_strategy_competition_multi(
    packets: Sequence[Mapping[str, Any] | dict[str, Any]] | None,
    *,
    calibration: dict[str, Any] | Mapping[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Compete each INGESTED free-first ingest and merge candidates.

    Skips non-INGESTED packets. Fail-closed NOT_COMPUTABLE when none ingested.
    Candidates sorted by descending score then identity keys. Advisory only.
    """
    rows = [p for p in (packets or []) if isinstance(p, Mapping)]
    ingested = [p for p in rows if p.get("status") == "INGESTED"]
    rid = str(
        run_id
        or (ingested[0].get("run_id") if ingested else None)
        or (rows[0].get("run_id") if rows else None)
        or "UNKNOWN"
    )

    if not ingested:
        out = not_computable(
            "StrategyCompetitionPacket.v1",
            "no_ingested_events",
            run_id=rid,
            event_id="MULTI",
            candidates=[],
            candidate_count=0,
            competed_event_count=0,
            ingest_count=len(rows),
        )
        assert_no_live_capital(out)
        return out

    merged: list[dict[str, Any]] = []
    strategy_ids: list[str] = []
    event_ids: list[str] = []
    model_edge_enabled = False
    for packet in ingested:
        part = run_strategy_competition(packet, calibration=calibration)
        if part.get("status") != "COMPUTED":
            continue
        if part.get("model_edge_enabled"):
            model_edge_enabled = True
        eid = str(packet.get("event_id") or part.get("event_id") or "UNKNOWN")
        event_ids.append(eid)
        for sid in (part.get("provenance") or {}).get("strategy_ids") or []:
            if sid not in strategy_ids:
                strategy_ids.append(str(sid))
        for c in part.get("candidates") or []:
            if not isinstance(c, Mapping):
                continue
            row = dict(c)
            row.setdefault("event_id", eid)
            prov = dict(row.get("provenance") or {})
            prov.setdefault("source_event_id", eid)
            prov.setdefault("multi_event_compete", True)
            row["provenance"] = prov
            row["authority"] = Authority.SHADOW_ONLY.value
            row["capital_authority"] = False
            row["execution_authority"] = False
            merged.append(row)

    merged.sort(key=_multi_sort_key)
    out: dict[str, Any] = {
        "schema_version": "StrategyCompetitionPacket.v1",
        "status": "COMPUTED",
        "run_id": rid,
        "event_id": "MULTI" if len(event_ids) > 1 else (event_ids[0] if event_ids else "UNKNOWN"),
        "candidates": merged,
        "candidate_count": len(merged),
        "authority": Authority.SHADOW_ONLY.value,
        "capital_authority": False,
        "execution_authority": False,
        "model_edge_enabled": model_edge_enabled,
        "competed_event_count": len(event_ids),
        "ingest_count": len(rows),
        "provenance": {
            "strategy_ids": strategy_ids,
            "event_ids": event_ids,
            "multi_event": len(event_ids) > 1,
        },
    }
    assert_no_live_capital(out)
    return out
