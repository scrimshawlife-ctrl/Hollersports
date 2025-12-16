"""
ABX-Core Modules

Encoded, deterministic modules for sports wagering filters and analysis.
"""

from abraxas.modules.scorer_under_gate import (
    GateConfig,
    GateDecision,
    backtest,
    scorer_under_gate,
)

__all__ = [
    "GateConfig",
    "GateDecision",
    "backtest",
    "scorer_under_gate",
]
