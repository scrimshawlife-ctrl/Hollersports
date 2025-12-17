"""
HollerSports Engine - ABX-Core compliant betting engine.

Modules:
- reset_state: Slate state management with provenance tracking
- slate_runner: Main slate processing orchestrator
- picks_generator: Pick selection and optimization
- simulation: Monte Carlo simulation engine
"""

from .reset_state import (
    RunState,
    SlateIdentity,
    MarketLineSnapshot,
    GameContextCache,
    CalibrationMemory,
    init_new_slate_state,
    assert_state_matches_inputs,
    hard_reset_runtime_artifacts,
    make_market_key,
    merge_calibration_delta,
)

__all__ = [
    "RunState",
    "SlateIdentity",
    "MarketLineSnapshot",
    "GameContextCache",
    "CalibrationMemory",
    "init_new_slate_state",
    "assert_state_matches_inputs",
    "hard_reset_runtime_artifacts",
    "make_market_key",
    "merge_calibration_delta",
]
