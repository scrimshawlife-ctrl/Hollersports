"""MARKET_CONSENSUS_EDGE — multi-book consensus / price agreement."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.strategies.base import BaseStrategy, build_candidate

# Design Phase 7 Step 2 threshold.
CONSENSUS_THRESHOLD = 0.6


class MarketConsensusEdge(BaseStrategy):
    strategy_id = "MARKET_CONSENSUS_EDGE"
    strategy_family = "MARKET"

    def generate(self, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
        run_id, event_id = self._run_event(packet)
        out: list[dict[str, Any]] = []
        for market in self._markets(packet):
            raw = market.get("consensus_score")
            if raw is None:
                continue
            try:
                consensus = float(raw)
            except (TypeError, ValueError):
                continue
            if consensus < CONSENSUS_THRESHOLD:
                continue
            market_id = str(market.get("market_id") or "UNKNOWN")
            selection = str(market.get("selection") or "UNKNOWN")
            out.append(
                build_candidate(
                    strategy_id=self.strategy_id,
                    strategy_family=self.strategy_family,
                    run_id=run_id,
                    event_id=str(market.get("event_id") or event_id),
                    market_id=market_id,
                    selection=selection,
                    score=consensus,
                    confidence=consensus,
                    features={
                        "consensus_score": consensus,
                        "threshold": CONSENSUS_THRESHOLD,
                    },
                    packet_refs={
                        "run_id": run_id,
                        "market_id": market_id,
                    },
                )
            )
        return out
