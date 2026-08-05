"""CLV_RETENTION_EDGE — open→close retention when closing lines attach."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.strategies.base import BaseStrategy, build_candidate


class ClvRetentionEdge(BaseStrategy):
    strategy_id = "CLV_RETENTION_EDGE"
    strategy_family = "MARKET"

    def generate(self, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
        run_id, event_id = self._run_event(packet)
        out: list[dict[str, Any]] = []
        for market in self._markets(packet):
            raw = market.get("clv_retention")
            if raw is None:
                continue
            try:
                clv = float(raw)
            except (TypeError, ValueError):
                continue
            # Threshold: clv_retention > 0
            if clv <= 0:
                continue
            market_id = str(market.get("market_id") or "UNKNOWN")
            selection = str(market.get("selection") or "UNKNOWN")
            # Positive CLV can exceed 1 in theory; clamp via build_candidate.
            out.append(
                build_candidate(
                    strategy_id=self.strategy_id,
                    strategy_family=self.strategy_family,
                    run_id=run_id,
                    event_id=str(market.get("event_id") or event_id),
                    market_id=market_id,
                    selection=selection,
                    score=clv,
                    confidence=min(1.0, clv),
                    features={"clv_retention": clv},
                    packet_refs={
                        "run_id": run_id,
                        "market_id": market_id,
                    },
                )
            )
        return out
