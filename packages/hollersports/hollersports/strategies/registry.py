"""Strategy registry: load market-first strategies; model edge gated off by default."""

from __future__ import annotations

from typing import Any

from hollersports.governance.authority import Authority
from hollersports.strategies.base import BaseStrategy
from hollersports.strategies.clv_retention_edge import ClvRetentionEdge
from hollersports.strategies.market_consensus_edge import MarketConsensusEdge
from hollersports.strategies.model_probability_edge import ModelProbabilityEdge
from hollersports.strategies.public_overreaction_fade import PublicOverreactionFade


def load_strategies(*, allow_model_edge: bool = False) -> list[BaseStrategy]:
    """Return strategy instances. MODEL_PROBABILITY_EDGE only when allow_model_edge."""
    strategies: list[BaseStrategy] = [
        MarketConsensusEdge(),
        PublicOverreactionFade(),
        ClvRetentionEdge(),
    ]
    if allow_model_edge:
        strategies.append(ModelProbabilityEdge())
    return strategies


def registry_packet() -> dict[str, Any]:
    """Shadow-only registry summary (no capital/execution authority)."""
    strategies = load_strategies(allow_model_edge=False)
    return {
        "schema_version": "StrategyRegistryPacket.v1",
        "status": "READY",
        "authority": Authority.SHADOW_ONLY.value,
        "capital_authority": False,
        "execution_authority": False,
        "strategy_ids": sorted(s.strategy_id for s in strategies),
        "model_edge_default": False,
        "provenance": {},
    }
