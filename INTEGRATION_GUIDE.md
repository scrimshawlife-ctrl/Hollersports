# HollerSports Engine Integration Guide

This guide explains how the state management system (`reset_state.py`) integrates with the rest of the HollerSports engine to prevent slate leakage and ensure deterministic, provenance-tracked betting analysis.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      SlateRunner                            │
│  (Main orchestrator - owns RunState instance)               │
└──────────────┬──────────────────────────────────────────────┘
               │
               ├─────► reset_state.py
               │       - init_new_slate_state()
               │       - assert_state_matches_inputs()
               │       - hard_reset_runtime_artifacts()
               │
               ├─────► simulation.py
               │       - run_monte_carlo_simulations()
               │       - Reads from state.market.lines
               │       - Writes to state.simulations
               │
               └─────► picks_generator.py
                       - select_optimal_picks()
                       - Reads from state.simulations
                       - Writes to state.picks
```

## Core Principles

### 1. State Isolation

Each slate gets a **fresh RunState** initialized via `init_new_slate_state()`. This ensures:

- No picks from prior slates leak into current analysis
- No simulations from prior slates are reused
- Game context is recomputed for each slate
- Calibration memory is controlled and explicit

### 2. Provenance Tracking

Every state change is fingerprinted and logged:

```python
state.slate.source_fingerprint  # Hash of games + lines inputs
state.market.fingerprint         # Hash of provider + lines
state.game_context.fingerprint   # Hash of computed context
state.calibration.fingerprint    # Hash of adjustments
```

### 3. Input Validation

Before processing, validate that state matches inputs:

```python
assert_state_matches_inputs(
    state,
    games_payload=games,
    lines_payload=lines,
    provider="PrizePicks",
)
```

This prevents accidentally using stale state with new data.

## Integration Points

### 1. Initializing a Slate

```python
from engine.slate_runner import SlateRunner

# Define your slate inputs
games_payload = {
    "games": [
        {
            "game_id": "NBA_20251217_LAL_BOS",
            "home_team": "BOS",
            "away_team": "LAL",
            "venue": "home",
            "start_time_utc": 1734469200,
        }
    ]
}

lines_payload = {
    # Market keys generated via make_market_key()
    "abc123...": {
        "sport": "NBA",
        "game_id": "NBA_20251217_LAL_BOS",
        "player_id": "player_123",
        "player_name": "LeBron James",
        "market": "PTS",
        "line": 25.5,
    }
}

# Initialize runner
runner = SlateRunner(
    slate_id="NBA_2025-12-17_EVENING",
    sport="NBA",
    provider="PrizePicks",
    games_payload=games_payload,
    lines_payload=lines_payload,
)
```

### 2. Running the Pipeline

```python
# Full pipeline: context → simulations → picks
results = runner.run_full_pipeline(
    sim_iterations=10000,
    pick_strategy="edge",
    min_edge=0.05,
)

print(f"Generated {results['stats']['total_picks']} picks")
print(f"Source fingerprint: {results['slate']['source_fingerprint']}")
```

### 3. Custom Integration

For more control, call each step manually:

```python
# Step 1: Validate inputs
runner.validate_inputs()

# Step 2: Compute game context
runner.compute_game_context()

# Step 3: Run simulations
runner.run_simulations(iterations=10000)

# Step 4: Generate picks
picks = runner.generate_picks(strategy="edge", min_edge=0.05)

# Step 5: Export state for storage
state_snapshot = runner.export_state()
```

## Preventing Slate Leakage

### What is Slate Leakage?

Slate leakage occurs when artifacts from a previous slate affect analysis of a new slate:

- ❌ Using yesterday's simulations for today's games
- ❌ Carrying over picks from a different slate
- ❌ Applying calibration adjustments from unrelated games

### How We Prevent It

1. **Fresh State Initialization**

   ```python
   # Each slate gets a brand-new state
   state = init_new_slate_state(
       slate_id="NBA_2025-12-17_EVENING",
       sport="NBA",
       provider="PrizePicks",
       games_payload=games,
       lines_payload=lines,
   )
   ```

2. **Input Validation Guards**

   ```python
   # Raises RuntimeError if inputs don't match state
   assert_state_matches_inputs(state, games_payload=games, ...)
   ```

3. **Explicit Calibration Control**

   ```python
   # Calibration memory is opt-in, never automatic
   state = init_new_slate_state(
       ...,
       keep_calibration_memory=True,  # Must be explicit
       prior_calibration=previous_calibration,
   )
   ```

4. **Runtime Artifact Reset**

   ```python
   # Clear simulations/picks without destroying calibration
   hard_reset_runtime_artifacts(state)
   ```

## Calibration Memory Management

Calibration adjustments (e.g., fatigue factors, tempo skews) can be preserved across slates **if explicitly opted-in**:

```python
# First slate: build calibration
runner1 = SlateRunner(...)
# ... process slate 1 ...
calibration_after_slate1 = runner1.state.calibration

# Second slate: merge calibration
runner2 = SlateRunner(
    ...,
    keep_calibration_memory=True,
    prior_calibration=calibration_after_slate1,
)
```

### Controlled Merge

Use `merge_calibration_delta()` for deterministic merging:

```python
from engine.reset_state import merge_calibration_delta

# Base calibration
base = CalibrationMemory(enabled=True)
base.adjustments = {
    "NBA:player:123": {"PTS_mean_delta": 1.0}
}

# New adjustments to merge
delta = {
    "NBA:player:123": {"PTS_mean_delta": 1.5},  # Update
    "NBA:player:456": {"AST_mean_delta": 0.3},  # Add new
}

merged = merge_calibration_delta(base, delta, allow_new_keys=True)
```

## Simulation Engine Integration

The simulation engine reads from `state.market.lines` and writes to `state.simulations`:

```python
# Example: engine/simulation.py
def run_monte_carlo_simulations(state, iterations=10000):
    simulations = {}

    for market_key, line_data in state.market.lines.items():
        # Simulate this market
        sim_result = _simulate_market(state, market_key, line_data, iterations)
        simulations[market_key] = sim_result

    return simulations
```

**Key integration points:**

- Read player base stats from your database/ABX-Core engine
- Apply game context from `state.game_context.by_game_id`
- Apply calibration from `state.calibration.adjustments`
- Return results keyed by `market_key`

## Picks Generator Integration

The picks generator reads from `state.simulations` and writes to `state.picks`:

```python
# Example: engine/picks_generator.py
def select_optimal_picks(state, strategy="edge", min_edge=0.05):
    picks = []

    for market_key, sim_result in state.simulations.items():
        # Calculate edge
        edge = calculate_edge(sim_result, state.market.lines[market_key])

        if edge >= min_edge:
            pick = build_pick(market_key, sim_result, edge)
            picks.append(pick)

    # Sort and return top picks
    picks.sort(key=lambda p: p["score"], reverse=True)
    return picks
```

**Key integration points:**

- Read simulated probabilities from `state.simulations`
- Read market lines from `state.market.lines`
- Apply calibration from `state.calibration.adjustments`
- Return structured pick dictionaries

## Testing State Isolation

Run the test suite to verify proper state isolation:

```bash
python -m pytest tests/test_state_isolation.py -v
```

Key tests:

- `test_fresh_state_no_carryover`: Ensures new states are clean
- `test_assert_state_matches_inputs_failure`: Validates guardrails work
- `test_multiple_slates_no_leakage`: Confirms no cross-slate contamination

## Common Patterns

### Pattern 1: Daily Slate Processing

```python
def process_daily_slate(date, sport, provider):
    # Fetch fresh data
    games = fetch_games_for_date(date, sport)
    lines = fetch_lines_from_provider(provider, date, sport)

    # Initialize runner
    runner = SlateRunner(
        slate_id=f"{sport}_{date}",
        sport=sport,
        provider=provider,
        games_payload=games,
        lines_payload=lines,
    )

    # Run pipeline
    results = runner.run_full_pipeline()

    # Store results
    store_results(results)

    return results
```

### Pattern 2: Backtest with Calibration Rollup

```python
calibration = CalibrationMemory(enabled=True)

for date in date_range:
    runner = SlateRunner(
        slate_id=f"NBA_{date}",
        sport="NBA",
        provider="PrizePicks",
        games_payload=fetch_games(date),
        lines_payload=fetch_lines(date),
        keep_calibration_memory=True,
        prior_calibration=calibration,
    )

    results = runner.run_full_pipeline()

    # Update calibration based on results
    calibration = update_calibration(calibration, results)
```

### Pattern 3: Re-run with Same Inputs

```python
# Initial run
runner = SlateRunner(...)
results1 = runner.run_full_pipeline()

# Re-run with different parameters (same inputs)
runner.validate_inputs()  # Ensure inputs still match
runner.reset_runtime_artifacts()  # Clear old simulations/picks
results2 = runner.run_full_pipeline(min_edge=0.08)  # Different threshold
```

## Provenance Inspection

Every RunState includes full provenance:

```python
state = runner.state

print(state.provenance["reset_policy"])
# {
#   "no_slate_bleed": True,
#   "keep_calibration_memory": False,
#   "calibration_merge_mode": "discard"
# }

print(state.provenance["inputs"])
# {
#   "games_fingerprint": "abc123...",
#   "lines_fingerprint": "def456...",
#   "slate_source_fingerprint": "ghi789...",
#   "provider": "PrizePicks"
# }
```

## Next Steps

1. **Integrate with your player database**: Replace placeholder stats in `simulation.py`
2. **Connect to ABX-Core engine**: Replace simulation logic with actual symbolic engine
3. **Add real game context computation**: Implement venue, rest, matchup factors
4. **Implement calibration updates**: Build feedback loop from results to calibration
5. **Add persistence layer**: Store states and results for audit trail

## Support

- Documentation: See inline comments in each module
- Tests: `tests/test_state_isolation.py`
- Examples: `examples/basic_usage.py`
