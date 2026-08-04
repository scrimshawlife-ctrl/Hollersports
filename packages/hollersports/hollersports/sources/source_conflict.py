"""Detect simple event conflicts across free-first sources (advisory observation)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from hollersports.governance.authority import Authority
from hollersports.schemas.hashing import packet_hash


def _team_set(event: Mapping[str, Any]) -> frozenset[str]:
    teams = event.get("teams") or []
    return frozenset(str(t).upper() for t in teams if t)


def detect_event_conflicts(
    *,
    left_events: Sequence[Mapping[str, Any]],
    right_events: Sequence[Mapping[str, Any]],
    left_source: str,
    right_source: str,
    run_id: str = "CONFLICT",
) -> dict[str, Any]:
    """Compare two event lists for team-set mismatches on shared ids or start windows.

    Fail-closed: missing sides → empty conflicts with status PARTIAL.
    Never emits recommendations or capital authority.
    """
    left_by_id = {
        str(e.get("event_id")): e
        for e in left_events
        if isinstance(e, Mapping) and e.get("event_id")
    }
    right_by_id = {
        str(e.get("event_id")): e
        for e in right_events
        if isinstance(e, Mapping) and e.get("event_id")
    }

    conflicts: list[dict[str, Any]] = []
    shared_ids = sorted(set(left_by_id) & set(right_by_id))
    for eid in shared_ids:
        lt = _team_set(left_by_id[eid])
        rt = _team_set(right_by_id[eid])
        if lt and rt and lt != rt:
            conflicts.append(
                {
                    "event_id": eid,
                    "kind": "team_set_mismatch",
                    "left_source": left_source,
                    "right_source": right_source,
                    "left_teams": sorted(lt),
                    "right_teams": sorted(rt),
                }
            )

    # Same-day team pairs present in only one source (informational)
    left_only = sorted(set(left_by_id) - set(right_by_id))
    right_only = sorted(set(right_by_id) - set(left_by_id))

    status = "CLEAR"
    if conflicts:
        status = "CONFLICT"
    elif left_only or right_only:
        status = "PARTIAL"

    packet = {
        "schema_version": "SourceConflictPacket.v1",
        "status": status,
        "run_id": run_id,
        "left_source": left_source,
        "right_source": right_source,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "left_only_event_ids": left_only[:50],
        "right_only_event_ids": right_only[:50],
        "authority": Authority.SHADOW_ONLY.value,
        "capital_authority": False,
        "execution_authority": False,
        "provenance": {
            "left_count": len(left_by_id),
            "right_count": len(right_by_id),
        },
    }
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k != "packet_hash"}
    )
    return packet
