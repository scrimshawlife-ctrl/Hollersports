"""Market ingestion pipeline: health gate → MarketIngestionPacket."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.governance.fail_closed import not_computable
from hollersports.runes.source_health import evaluate_source_health
from hollersports.schemas.packets import MarketIngestionPacket

_VALID_SOURCE_TYPES = frozenset(
    {"ESPN", "ODDS_FEED", "MANUAL", "FIXTURE", "UNKNOWN"}
)


def _finalize(packet_dict: dict[str, Any]) -> dict[str, Any]:
    """Never surface recommendations; enforce capital locks on every exit."""
    packet_dict.pop("recommendation", None)
    assert_no_live_capital(packet_dict)
    return packet_dict


def run_market_ingestion(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate source health and emit a MarketIngestionPacket dict.

    - health FAIL → status REJECTED
    - health NOT_COMPUTABLE → status NOT_COMPUTABLE
    - health PASS / WARN → status INGESTED with markets and source_health
    """
    if not isinstance(payload, Mapping):
        return _finalize(
            not_computable(
                "MarketIngestionPacket.v1",
                "invalid_ingest_payload",
                run_id="UNKNOWN",
                source_id="UNKNOWN",
                markets=[],
            )
        )

    run_id = str(payload.get("run_id") or "UNKNOWN")
    source_id = str(payload.get("source_id") or "UNKNOWN")
    raw_type = str(payload.get("source_type") or "UNKNOWN")
    source_type = raw_type if raw_type in _VALID_SOURCE_TYPES else "UNKNOWN"
    fetched_at = str(payload.get("fetched_at") or "")
    current_time = str(payload.get("current_time") or "")
    required_fields = list(payload.get("required_fields") or [])
    source_refs = payload.get("source_refs")
    if source_refs is not None and not isinstance(source_refs, Mapping):
        source_refs = None
    event_payload = payload.get("payload")
    if not isinstance(event_payload, Mapping):
        event_payload = {}

    health = evaluate_source_health(
        event_payload,
        source_id=source_id,
        fetched_at=fetched_at,
        current_time=current_time,
        required_fields=required_fields,
        source_refs=source_refs,
    )

    refs = dict(source_refs) if isinstance(source_refs, Mapping) else {}
    base_kwargs: dict[str, Any] = {
        "run_id": run_id,
        "source_id": source_id,
        "source_type": source_type,  # type: ignore[arg-type]
        "fetched_at": fetched_at,
        "event_id": str(event_payload.get("event_id") or "UNKNOWN"),
        "sport": str(event_payload.get("sport") or "UNKNOWN"),
        "league": str(event_payload.get("league") or "UNKNOWN"),
        "teams": list(event_payload.get("teams") or []),
        "source_refs": refs,
        "source_health": health,
        "authority": Authority.SHADOW_ONLY.value,
        "capital_authority": False,
        "execution_authority": False,
        "provenance": {
            "source_refs": refs,
            "fetched_at": fetched_at,
            "source_id": source_id,
        },
    }

    status = health.get("status")

    if status == "NOT_COMPUTABLE":
        out = not_computable(
            "MarketIngestionPacket.v1",
            str(health.get("reason") or "source_health_not_computable"),
            **{
                k: v
                for k, v in base_kwargs.items()
                if k
                not in {
                    "authority",
                    "capital_authority",
                    "execution_authority",
                    "provenance",
                }
            },
            markets=[],
        )
        return _finalize(out)

    if status == "FAIL":
        packet = MarketIngestionPacket(
            status="REJECTED",
            markets=[],
            reason=str(health.get("reason") or "source_health_fail"),
            **base_kwargs,
        )
        return _finalize(packet.model_dump())

    markets = list(event_payload.get("markets") or [])
    packet = MarketIngestionPacket(
        status="INGESTED",
        markets=markets,
        reason=str(health.get("reason")) if health.get("reason") else None,
        **base_kwargs,
    )
    return _finalize(packet.model_dump())
