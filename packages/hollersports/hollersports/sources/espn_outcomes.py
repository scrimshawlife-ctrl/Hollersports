"""ESPN scoreboard finals → advisory settlement result rows (no money).

Fail-closed: non-final games emit PENDING. Never invents winners.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


_COMPLETED_NAMES = frozenset(
    {
        "STATUS_FINAL",
        "STATUS_FULL_TIME",
        "STATUS_FINAL_PEN",
        "STATUS_FINAL_AET",
        "Final",
    }
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _competitor_label(comp: Mapping[str, Any]) -> str:
    team = comp.get("team") if isinstance(comp.get("team"), Mapping) else {}
    return str(
        team.get("abbreviation")
        or team.get("displayName")
        or team.get("shortDisplayName")
        or ""
    ).strip()


def _parse_score(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _event_completed(event: Mapping[str, Any]) -> bool:
    status = event.get("status")
    if not isinstance(status, Mapping):
        return False
    stype = status.get("type")
    if not isinstance(stype, Mapping):
        return False
    if stype.get("completed") is True:
        return True
    name = str(stype.get("name") or "")
    state = str(stype.get("state") or "").lower()
    if name in _COMPLETED_NAMES:
        return True
    if state == "post":
        return True
    return False


def normalize_espn_moneyline_results(
    raw: Mapping[str, Any],
    *,
    league: str = "NBA",
    settled_at: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize ESPN scoreboard events to settlement result rows.

    Each competitor becomes a selection-keyed result:
      - completed + winner True → WIN
      - completed + winner False → LOSS
      - completed + tied scores → PUSH (both)
      - not completed / missing scores → PENDING

    Never invents winners. ``source`` is always ``ESPN_SCOREBOARD``.
    """
    league_key = str(league or "NBA").strip().upper() or "NBA"
    when = settled_at or _now_iso()
    out: list[dict[str, Any]] = []

    for event in raw.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        eid = str(event.get("id") or "UNKNOWN")
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions else {}
        if not isinstance(competition, Mapping):
            competition = {}
        competitors = [
            c for c in (competition.get("competitors") or []) if isinstance(c, Mapping)
        ]
        completed = _event_completed(event)
        scores = [_parse_score(c.get("score")) for c in competitors]
        score_parts = [
            str(int(s)) if s is not None and s == int(s) else (str(s) if s is not None else "?")
            for s in scores
        ]
        final_score = "-".join(score_parts) if any(s is not None for s in scores) else None

        # Resolve winners from ESPN winner flag, else score compare when final.
        winners: list[bool | None] = []
        for c in competitors:
            if c.get("winner") is True:
                winners.append(True)
            elif c.get("winner") is False:
                winners.append(False)
            else:
                winners.append(None)

        if completed and all(w is None for w in winners) and all(s is not None for s in scores):
            if len(scores) >= 2 and scores[0] == scores[1]:
                winners = [None for _ in competitors]  # PUSH via scores
            elif len(scores) >= 2:
                best = max(s for s in scores if s is not None)
                winners = [True if s == best else False for s in scores]

        tied = (
            completed
            and len(scores) >= 2
            and all(s is not None for s in scores)
            and scores[0] == scores[1]
        )

        for idx, comp in enumerate(competitors):
            selection = _competitor_label(comp)
            if not selection:
                continue
            if not completed:
                result = "PENDING"
            elif tied:
                result = "PUSH"
            else:
                w = winners[idx] if idx < len(winners) else None
                if w is True:
                    result = "WIN"
                elif w is False:
                    result = "LOSS"
                else:
                    result = "PENDING"

            out.append(
                {
                    "event_id": eid,
                    "market_id": "",
                    "selection": selection,
                    "result": result,
                    "source": "ESPN_SCOREBOARD",
                    "result_source": "ESPN_SCOREBOARD",
                    "final_score": final_score,
                    "settled_at": when if result != "PENDING" else "",
                    "league": league_key,
                    "provenance": {
                        "espn_event_id": eid,
                        "completed": completed,
                        "home_away": comp.get("homeAway"),
                    },
                }
            )
    return out


def merge_espn_moneyline_results(
    packs: Sequence[tuple[Mapping[str, Any], str]],
    *,
    settled_at: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize multiple (raw, league) ESPN scoreboards into one result list."""
    merged: list[dict[str, Any]] = []
    for raw, league in packs:
        if not isinstance(raw, Mapping):
            continue
        merged.extend(
            normalize_espn_moneyline_results(
                raw, league=league, settled_at=settled_at
            )
        )
    return merged
