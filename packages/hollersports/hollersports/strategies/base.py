"""Base strategy interface and candidate builder."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from hollersports.governance.authority import Authority
from hollersports.schemas.packets import StrategyCandidatePacket


def build_candidate(
    *,
    strategy_id: str,
    run_id: str,
    event_id: str,
    market_id: str,
    selection: str,
    strategy_family: str = "",
    score: float = 0.0,
    confidence: float = 0.0,
    features: Mapping[str, Any] | None = None,
    packet_refs: Mapping[str, Any] | None = None,
    reason: str | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a StrategyCandidatePacket dict.

    Always SHADOW_ONLY with capital_authority and execution_authority false.
    """
    # Clamp score/confidence into schema range [0, 1].
    score_v = max(0.0, min(1.0, float(score)))
    conf_v = max(0.0, min(1.0, float(confidence)))
    packet = StrategyCandidatePacket(
        status="CANDIDATE",
        run_id=str(run_id),
        strategy_id=str(strategy_id),
        strategy_family=str(strategy_family or ""),
        event_id=str(event_id),
        market_id=str(market_id),
        selection=str(selection),
        score=score_v,
        confidence=conf_v,
        features=dict(features or {}),
        packet_refs=dict(packet_refs or {}),
        authority=Authority.SHADOW_ONLY.value,
        capital_authority=False,
        execution_authority=False,
        provenance=dict(provenance or {}),
        reason=reason,
    )
    out = packet.model_dump()
    assert out["authority"] == Authority.SHADOW_ONLY.value
    assert out["capital_authority"] is False
    assert out["execution_authority"] is False
    return out


class BaseStrategy(ABC):
    """Pure strategy: MarketIngestionPacket → list of candidate dicts."""

    strategy_id: str = ""
    strategy_family: str = "MARKET"

    @abstractmethod
    def generate(self, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Emit zero or more SHADOW_ONLY candidates from an ingested market packet."""

    def _markets(self, packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        markets = packet.get("markets") or []
        if not isinstance(markets, list):
            return []
        return [m for m in markets if isinstance(m, Mapping)]

    def _run_event(self, packet: Mapping[str, Any]) -> tuple[str, str]:
        run_id = str(packet.get("run_id") or "UNKNOWN")
        event_id = str(packet.get("event_id") or "UNKNOWN")
        return run_id, event_id
