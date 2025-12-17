# FILE: hollersports/cli/run_slate.py
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

from hollersports.engine.reset_state import (
    init_new_slate_state,
    assert_state_matches_inputs,
    hard_reset_runtime_artifacts,
)

def _load(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main(argv: List[str]) -> int:
    """
    Usage:
      python -m hollersports.cli.run_slate games.json lines.json
    This establishes a clean RunState and validates fingerprints.
    """
    if len(argv) < 3:
        print("Usage: python -m hollersports.cli.run_slate games.json lines.json")
        return 2

    games_payload: Dict[str, Any] = _load(argv[1])
    lines_payload: Dict[str, Any] = _load(argv[2])

    state = init_new_slate_state(
        slate_id="AUTO_SLATE",
        sport=str(games_payload.get("sport", "NBA")),
        provider=str(lines_payload.get("provider", "UnknownProvider")),
        games_payload=games_payload,
        lines_payload=lines_payload.get("lines", lines_payload),
    )

    # Prove no mismatch
    assert_state_matches_inputs(
        state,
        games_payload=games_payload,
        lines_payload=lines_payload.get("lines", lines_payload),
        provider=str(lines_payload.get("provider", "UnknownProvider")),
    )

    # Demonstrate hard reset works (within-slate recalcs)
    hard_reset_runtime_artifacts(state)

    print(json.dumps({
        "ok": True,
        "slate_fingerprint": state.slate.source_fingerprint,
        "market_fingerprint": state.market.fingerprint,
        "calibration_count": len(state.calibration.adjustments),
        "reset_policy": state.provenance.get("reset_policy", {}),
    }, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
