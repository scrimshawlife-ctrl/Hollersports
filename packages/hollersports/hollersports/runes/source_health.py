"""Source health evaluation (freshness, required fields, provenance)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from hollersports.governance.authority import Authority
from hollersports.schemas.packets import SourceHealthPacket


def _parse_time(value: str) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def evaluate_source_health(
    payload: Mapping[str, Any] | None,
    *,
    source_id: str,
    fetched_at: str,
    current_time: str,
    required_fields: Sequence[str],
    source_refs: Mapping[str, Any] | None,
    stale_after_seconds: float = 900,
) -> dict[str, Any]:
    """Evaluate source freshness, required fields, and provenance presence.

    Rules (design Phase 7 / §7.2):
    - Missing required fields or missing provenance → FAIL
    - Stale (freshness > stale_after_seconds) → WARN
    - Else → PASS
    - health_score in [0, 1]; never emits recommendations
    """
    data: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}

    missing = [f for f in required_fields if f not in data or data.get(f) is None]
    provenance_present = bool(source_refs)

    fetched = _parse_time(fetched_at)
    current = _parse_time(current_time)
    if fetched is None or current is None:
        packet = SourceHealthPacket(
            status="NOT_COMPUTABLE",
            source_id=source_id,
            freshness_seconds=0.0,
            missing_required_fields=list(missing),
            stale=False,
            provenance_present=provenance_present,
            health_score=0.0,
            authority=Authority.SHADOW_ONLY.value,
            reason="invalid_timestamps",
            provenance={},
        )
        return packet.model_dump()

    freshness_seconds = max(0.0, (current - fetched).total_seconds())
    stale = freshness_seconds > float(stale_after_seconds)

    if missing or not provenance_present:
        reasons: list[str] = []
        if missing:
            reasons.append("missing_required_fields")
        if not provenance_present:
            reasons.append("missing_provenance")
        packet = SourceHealthPacket(
            status="FAIL",
            source_id=source_id,
            freshness_seconds=freshness_seconds,
            missing_required_fields=list(missing),
            stale=stale,
            provenance_present=provenance_present,
            health_score=0.0,
            authority=Authority.SHADOW_ONLY.value,
            reason="+".join(reasons),
            provenance=dict(source_refs) if source_refs else {},
        )
        return packet.model_dump()

    if stale:
        # Decay score for over-stale feeds; still ingestable with WARN flag.
        ratio = float(stale_after_seconds) / max(freshness_seconds, 1e-9)
        health_score = max(0.0, min(1.0, 0.5 * ratio))
        packet = SourceHealthPacket(
            status="WARN",
            source_id=source_id,
            freshness_seconds=freshness_seconds,
            missing_required_fields=[],
            stale=True,
            provenance_present=True,
            health_score=health_score,
            authority=Authority.SHADOW_ONLY.value,
            reason="stale",
            provenance=dict(source_refs),
        )
        return packet.model_dump()

    # PASS: full score when brand-new; mild decay as age approaches threshold.
    if stale_after_seconds <= 0:
        health_score = 1.0
    else:
        age_ratio = freshness_seconds / float(stale_after_seconds)
        health_score = max(0.0, min(1.0, 1.0 - 0.25 * age_ratio))

    packet = SourceHealthPacket(
        status="PASS",
        source_id=source_id,
        freshness_seconds=freshness_seconds,
        missing_required_fields=[],
        stale=False,
        provenance_present=True,
        health_score=health_score,
        authority=Authority.SHADOW_ONLY.value,
        provenance=dict(source_refs),
    )
    return packet.model_dump()
