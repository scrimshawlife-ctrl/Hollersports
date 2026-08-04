"""Detect simple event conflicts across free-first sources (advisory observation)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from hollersports.governance.authority import Authority
from hollersports.schemas.hashing import packet_hash

# Default window for team-set + start-time proximity joins (12h covers delayed tips).
_DEFAULT_MAX_START_DELTA_SECONDS = 12 * 3600.0


def _team_set(event: Mapping[str, Any]) -> frozenset[str]:
    """Normalized team tokens (uppercased). Prefer explicit teams list."""
    teams = list(event.get("teams") or [])
    home = event.get("home_team")
    away = event.get("away_team")
    for t in (away, home):
        if t and str(t) not in teams:
            teams.append(str(t))
    return frozenset(str(t).strip().upper() for t in teams if t and str(t).strip())


def _parse_start(event: Mapping[str, Any]) -> datetime | None:
    raw = event.get("start_time") or event.get("commence_time") or event.get("date")
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def join_events_by_teams(
    left_events: Sequence[Mapping[str, Any]],
    right_events: Sequence[Mapping[str, Any]],
    *,
    max_start_delta_seconds: float = _DEFAULT_MAX_START_DELTA_SECONDS,
) -> list[dict[str, Any]]:
    """1-1 join events across sources by event_id, else team set + start proximity.

    Matching order per left event:
      1. Same ``event_id`` (if present and unused on right)
      2. Identical normalized team set with closest start_time within
         ``max_start_delta_seconds``
      3. Identical team set with no usable timestamps (``teams_only``)

    Returns join rows (left_only / right_only for unmatched). Advisory only —
    never emits capital or execution authority.
    """
    left_list = [e for e in left_events if isinstance(e, Mapping)]
    right_list = [e for e in right_events if isinstance(e, Mapping)]

    used_right: set[int] = set()
    joins: list[dict[str, Any]] = []

    right_by_id: dict[str, list[int]] = {}
    for i, e in enumerate(right_list):
        eid = str(e.get("event_id") or "")
        if eid and eid != "UNKNOWN":
            right_by_id.setdefault(eid, []).append(i)

    unmatched_left: list[int] = []

    def _row(
        *,
        left: Mapping[str, Any] | None,
        right: Mapping[str, Any] | None,
        match_kind: str,
        start_delta_seconds: float | None,
        team_set: frozenset[str],
    ) -> dict[str, Any]:
        return {
            "left": dict(left) if left is not None else None,
            "right": dict(right) if right is not None else None,
            "team_set": sorted(team_set),
            "match_kind": match_kind,
            "start_delta_seconds": start_delta_seconds,
            "left_event_id": (left or {}).get("event_id") if left else None,
            "right_event_id": (right or {}).get("event_id") if right else None,
        }

    for li, left in enumerate(left_list):
        eid = str(left.get("event_id") or "")
        matched_ri: int | None = None
        if eid and eid != "UNKNOWN" and eid in right_by_id:
            for ri in right_by_id[eid]:
                if ri not in used_right:
                    matched_ri = ri
                    break
        if matched_ri is None:
            unmatched_left.append(li)
            continue

        used_right.add(matched_ri)
        right = right_list[matched_ri]
        lt, rt = _parse_start(left), _parse_start(right)
        delta: float | None = None
        if lt is not None and rt is not None:
            delta = abs((lt - rt).total_seconds())
        joins.append(
            _row(
                left=left,
                right=right,
                match_kind="event_id",
                start_delta_seconds=delta,
                team_set=_team_set(left) | _team_set(right),
            )
        )

    for li in unmatched_left:
        left = left_list[li]
        lteams = _team_set(left)
        lstart = _parse_start(left)
        best_ri: int | None = None
        best_delta: float | None = None
        best_kind = "teams_only"

        for ri, right in enumerate(right_list):
            if ri in used_right:
                continue
            rteams = _team_set(right)
            if not lteams or not rteams or lteams != rteams:
                continue
            rstart = _parse_start(right)
            if lstart is not None and rstart is not None:
                d = abs((lstart - rstart).total_seconds())
                if d > max_start_delta_seconds:
                    continue
                if best_delta is None or d < best_delta:
                    best_ri = ri
                    best_delta = d
                    best_kind = "teams_start"
            elif best_ri is None and best_delta is None:
                # Accept teams-only only if no timed candidate claimed yet.
                # Prefer timed matches: skip if we already have a timed best.
                if best_kind != "teams_start":
                    best_ri = ri
                    best_delta = None
                    best_kind = "teams_only"

        if best_ri is not None:
            used_right.add(best_ri)
            right = right_list[best_ri]
            joins.append(
                _row(
                    left=left,
                    right=right,
                    match_kind=best_kind,
                    start_delta_seconds=best_delta,
                    team_set=lteams,
                )
            )
        else:
            joins.append(
                _row(
                    left=left,
                    right=None,
                    match_kind="left_only",
                    start_delta_seconds=None,
                    team_set=lteams,
                )
            )

    for ri, right in enumerate(right_list):
        if ri in used_right:
            continue
        joins.append(
            _row(
                left=None,
                right=right,
                match_kind="right_only",
                start_delta_seconds=None,
                team_set=_team_set(right),
            )
        )

    return joins


def detect_event_conflicts(
    *,
    left_events: Sequence[Mapping[str, Any]],
    right_events: Sequence[Mapping[str, Any]],
    left_source: str,
    right_source: str,
    run_id: str = "CONFLICT",
    max_start_delta_seconds: float = _DEFAULT_MAX_START_DELTA_SECONDS,
) -> dict[str, Any]:
    """Compare two event lists via event_id and team-set + start proximity joins.

    Conflicts: shared event_id (or team join) with disagreeing team sets.
    PARTIAL: unmatched left_only / right_only after team joins.
    CLEAR: every side paired (by id or teams) with no team mismatches.

    Fail-closed: empty inputs → PARTIAL when one side empty, CLEAR when both empty.
    Never emits recommendations or capital authority.
    """
    joins = join_events_by_teams(
        left_events,
        right_events,
        max_start_delta_seconds=max_start_delta_seconds,
    )

    conflicts: list[dict[str, Any]] = []
    for j in joins:
        left = j.get("left")
        right = j.get("right")
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            continue
        lt = _team_set(left)
        rt = _team_set(right)
        if lt and rt and lt != rt:
            conflicts.append(
                {
                    "event_id": str(
                        left.get("event_id") or right.get("event_id") or "UNKNOWN"
                    ),
                    "kind": "team_set_mismatch",
                    "left_source": left_source,
                    "right_source": right_source,
                    "left_teams": sorted(lt),
                    "right_teams": sorted(rt),
                    "match_kind": j.get("match_kind"),
                    "left_event_id": j.get("left_event_id"),
                    "right_event_id": j.get("right_event_id"),
                }
            )

    left_only = [
        str(j["left_event_id"])
        for j in joins
        if j.get("match_kind") == "left_only" and j.get("left_event_id") is not None
    ]
    right_only = [
        str(j["right_event_id"])
        for j in joins
        if j.get("match_kind") == "right_only" and j.get("right_event_id") is not None
    ]

    matched_kinds = {"event_id", "teams_start", "teams_only"}
    matched = [j for j in joins if j.get("match_kind") in matched_kinds]

    status = "CLEAR"
    if conflicts:
        status = "CONFLICT"
    elif left_only or right_only:
        status = "PARTIAL"
    elif not left_events and not right_events:
        status = "CLEAR"
    elif not left_events or not right_events:
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
        "joins": [
            {
                "match_kind": j.get("match_kind"),
                "team_set": j.get("team_set"),
                "start_delta_seconds": j.get("start_delta_seconds"),
                "left_event_id": j.get("left_event_id"),
                "right_event_id": j.get("right_event_id"),
            }
            for j in joins
        ],
        "authority": Authority.SHADOW_ONLY.value,
        "capital_authority": False,
        "execution_authority": False,
        "provenance": {
            "left_count": sum(1 for e in left_events if isinstance(e, Mapping)),
            "right_count": sum(1 for e in right_events if isinstance(e, Mapping)),
            "matched_count": len(matched),
            "join_count": len(joins),
            "max_start_delta_seconds": max_start_delta_seconds,
        },
    }
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k != "packet_hash"}
    )
    return packet
