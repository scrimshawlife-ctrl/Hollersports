"""PUBLIC_OVERREACTION_FADE — public vs handle gap when splits available."""

from __future__ import annotations

from typing import Any, Mapping

from hollersports.strategies.base import BaseStrategy, build_candidate

# Design Phase 7 Step 2 thresholds.
PUBLIC_BET_THRESHOLD = 0.7
GAP_THRESHOLD = 0.15


class PublicOverreactionFade(BaseStrategy):
    strategy_id = "PUBLIC_OVERREACTION_FADE"
    strategy_family = "MARKET"

    def generate(self, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
        run_id, event_id = self._run_event(packet)
        out: list[dict[str, Any]] = []
        for market in self._markets(packet):
            # Never invent public splits: both fields must be present.
            if market.get("public_bet_pct") is None or market.get("handle_pct") is None:
                continue
            try:
                public_bet_pct = float(market["public_bet_pct"])
                handle_pct = float(market["handle_pct"])
            except (TypeError, ValueError):
                continue
            gap = abs(public_bet_pct - handle_pct)
            if public_bet_pct < PUBLIC_BET_THRESHOLD or gap < GAP_THRESHOLD:
                continue
            market_id = str(market.get("market_id") or "UNKNOWN")
            # Fade the public side; require explicit fade_selection (no invention).
            fade_selection = market.get("fade_selection")
            if fade_selection is None or fade_selection == "":
                continue
            selection = str(fade_selection)
            score = min(1.0, gap)
            out.append(
                build_candidate(
                    strategy_id=self.strategy_id,
                    strategy_family=self.strategy_family,
                    run_id=run_id,
                    event_id=str(market.get("event_id") or event_id),
                    market_id=market_id,
                    selection=selection,
                    score=score,
                    confidence=min(1.0, public_bet_pct),
                    features={
                        "public_bet_pct": public_bet_pct,
                        "handle_pct": handle_pct,
                        "gap": gap,
                        "public_bet_threshold": PUBLIC_BET_THRESHOLD,
                        "gap_threshold": GAP_THRESHOLD,
                    },
                    packet_refs={
                        "run_id": run_id,
                        "market_id": market_id,
                    },
                )
            )
        return out
