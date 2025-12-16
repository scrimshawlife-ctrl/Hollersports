# Contextual Correction Map (CCM) - Venue/Coach Adjustments

**Internal calibration layer for learning context-regime corrections from historical prop outcomes**

## Overview

The CCM subsystem learns systematic residual biases by context (venue, coach, travel, matchup) and applies corrections to raw projections before bet slip construction. This improves projection accuracy without changing the user-facing selection logic.

### Key Principle

**Lines are not perfect.** Bookmakers may systematically misprice props in certain contexts:
- **Venue effects**: Some arenas suppress scoring (tight spacing, altitude, defensive home advantage)
- **Coaching philosophy**: Usage concentration, rotation depth, pace preferences
- **Travel factors**: Back-to-back games, timezone shifts, rest days
- **Matchup schemes**: Defensive rating, pace, opponent compression

The CCM learns these biases from historical outcomes and adjusts projections accordingly.

## Architecture

```
Raw Projection (25.0)
         ↓
   [CCM Layer]  ← Contextual Correction Map
         ↓      (learns: TD Garden home PTS = -1.2 avg)
Adjusted Projection (23.8)
         ↓
  Selection Logic
  (Higher/Lower decision)
```

## How It Works

### 1. Training Phase

Input: Historical prop records with outcomes
```python
PropRecord(
    player_id="jayson_tatum",
    market="PTS",
    line=28.5,
    actual=26.0,  # Residual = -2.5
    venue_id="TD_Garden",
    coach_id="coach_stevens",
    ...
)
```

Process:
1. **Feature Engineering**: Hash categorical values (venue, coach) to bounded buckets
2. **Grouping**: Aggregate by context key (market, venue_bucket, coach_bucket, is_home, travel, timezone)
3. **Statistics**: Compute mean/median residual, sample size, dispersion
4. **Shrinkage**: Apply Bayesian shrinkage toward zero based on sample size
   ```
   adjusted_delta = raw_mean * (count / (count + k))
   confidence = min(0.95, sqrt(count) / sqrt(count + k))
   ```
5. **Persistence**: Save to `correction_maps.json`

### 2. Runtime Phase

Input: Raw projection + context

Process:
1. **Hash features**: Convert venue/coach IDs to buckets (deterministic)
2. **Lookup correction**: Find matching context in CCM
3. **Fallback ladder** (if exact match not found):
   - Level 1: Full key (venue + coach + timezone + home + b2b)
   - Level 2: Drop timezone (venue + coach + home + b2b)
   - Level 3: Drop coach (venue + home + b2b)
   - Level 4: Return 0.0 (no correction)
4. **Apply adjustment**: `adjusted = raw + delta`

Each fallback level reduces confidence by decay factor (default 0.8).

## Data Schema

### Input Format (JSONL)

One JSON object per line:

```json
{
  "player_id": "jayson_tatum",
  "game_id": "20240115_BOS_LAL",
  "market": "PTS",
  "line": 28.5,
  "actual": 26.0,
  "side": "lower",
  "timestamp": "2024-01-15T19:00:00Z",
  "team_id": "BOS",
  "opp_id": "LAL",
  "venue_id": "TD_Garden",
  "is_home": true,
  "coach_id": "coach_stevens",
  "travel_b2b": false,
  "timezone_delta": 0,
  "rest_days": 2,
  "model_projection": 27.0
}
```

### Required Fields

- `player_id`, `game_id`, `market`, `line`, `actual`, `side`, `timestamp`
- `team_id`, `opp_id`, `venue_id`, `is_home`

### Optional Fields

- `coach_id`, `travel_b2b`, `timezone_delta`, `rest_days`
- `rotation_depth_proxy`, `pace_proxy`, `opponent_defense_proxy`, `scheme_proxy`
- `model_projection` (required for backtest evaluation)

## Running a Backtest

### Step 1: Prepare Data

Export historical prop legs to JSONL format:

```bash
# Example: export from your tracking system
python scripts/export_props_to_jsonl.py \
  --start-date 2023-10-01 \
  --end-date 2024-03-01 \
  --output data/props_202324_season.jsonl
```

### Step 2: Run Backtest

```python
from pathlib import Path
from hollersports.calibration.venue_coach_adjustments.backtest_runner import run_backtest

config = {
    "shrinkage": {
        "k": 25,           # Shrinkage parameter
        "min_samples": 5,  # Minimum samples per correction
    },
    "hash_buckets": {
        "venue": 100,
        "coach": 50,
        "team": 32,
        "opponent": 32,
    },
    "fallback_confidence_decay": 0.8,
}

report = run_backtest(
    input_path=Path("data/props_202324_season.jsonl"),
    output_dir=Path("output/ccm_v1"),
    config=config,
    seed=1337,
    train_fraction=0.8,
)

print(f"Baseline hit rate: {report['baseline']['hit_rate']:.1%}")
print(f"Corrected hit rate: {report['corrected']['hit_rate']:.1%}")
print(f"Improvement: {report['improvement']['hit_rate_delta']:+.1%}")
```

### Step 3: Deploy CCM

```bash
# Copy correction_maps.json to runtime location
cp output/ccm_v1/correction_maps.json \
   hollersports/calibration/venue_coach_adjustments/correction_maps.json
```

## Runtime Integration

### Initialize at Startup

```python
from hollersports.calibration.apply_adjustments import initialize_ccm

# Application startup
initialize_ccm()  # Loads from default path
```

### Apply Adjustments

```python
from hollersports.calibration.apply_adjustments import apply_adjustment
from hollersports.calibration.venue_coach_adjustments.models import PropMarket

# In your projection pipeline
raw_projection = my_model.predict(player, opponent, ...)

# Apply CCM adjustment
adjusted_projection = apply_adjustment(
    projection=raw_projection,
    market=PropMarket.PTS,
    context=game_context,
    record=prop_record,  # For feature building
)

# Use adjusted projection for selection
pick_higher = adjusted_projection > line
```

### Configuration Toggle

```bash
# Enable CCM (default)
export HOLLERSPORTS_CCM_ENABLED=true

# Disable CCM (use raw projections)
export HOLLERSPORTS_CCM_ENABLED=false
```

### Check Status

```python
from hollersports.calibration.apply_adjustments import get_ccm_status

status = get_ccm_status()
print(status)
# {
#   "enabled": True,
#   "loaded": True,
#   "entry_count": 147,
#   "provenance": {"run_id": "abc123", "created_at": "2024-01-15T..."}
# }
```

## Configuration Parameters

### Shrinkage

```yaml
shrinkage:
  k: 25              # Shrinkage toward zero (higher = more shrinkage)
  min_samples: 5     # Minimum samples to include correction
```

**Tuning guidance:**
- Higher `k` → more conservative (less extreme corrections)
- Lower `k` → more aggressive (trust small samples more)
- Default `k=25` balances bias-variance tradeoff

### Hash Buckets

```yaml
hash_buckets:
  venue: 100    # 100 venue buckets
  coach: 50     # 50 coach buckets
  team: 32      # 32 team buckets
  opponent: 32  # 32 opponent buckets
```

**Tuning guidance:**
- More buckets → finer granularity, but more keys → sparser data
- Fewer buckets → more data per key, but more collision/smoothing
- Default values balance granularity vs sample size

### Fallback Confidence Decay

```yaml
fallback_confidence_decay: 0.8
```

Each fallback step multiplies confidence by this factor.

## Provenance & Determinism

Every CCM artifact includes full provenance:

```json
{
  "provenance": {
    "run_id": "a1b2c3d4",
    "created_at": "2024-01-15T10:30:00Z",
    "seed": 1337,
    "inputs_hash": "e5f6g7h8",
    "config_hash": "i9j0k1l2",
    "schema_version": "1.0.0",
    "git_sha": "m3n4o5p6"
  }
}
```

**Guarantees:**
- Same inputs + config + seed → **identical CCM** (byte-for-byte)
- No hidden state, no random drift
- Full audit trail for regulatory compliance

## Testing

Run comprehensive test suite:

```bash
pytest tests/test_feature_builder.py -v
pytest tests/test_correction_fit.py -v
pytest tests/test_apply_adjustments.py -v
```

All tests use deterministic synthetic data (seed=1337) with no external dependencies.

## Performance Characteristics

- **Lookup time**: O(1) hash table lookup with ~3 fallback levels
- **Memory footprint**: ~10KB per 100 correction entries (typical: 100-500 entries)
- **Load time**: <100ms for typical CCM
- **Thread-safe**: Immutable dataclasses, safe for concurrent reads

## Monitoring & Debugging

### Backtest Report

```json
{
  "baseline": {
    "total": 1000,
    "correct": 580,
    "hit_rate": 0.58,
    "mae": 3.2
  },
  "corrected": {
    "total": 1000,
    "correct": 625,
    "hit_rate": 0.625,
    "mae": 2.8
  },
  "improvement": {
    "hit_rate_delta": 0.045,
    "mae_delta": 0.4
  }
}
```

### Common Issues

**Issue**: CCM not loading
- **Check**: `correction_maps.json` exists in expected location
- **Solution**: Run backtest to generate CCM or check `HOLLERSPORTS_CCM_ENABLED`

**Issue**: All adjustments are zero
- **Check**: Fallback ladder exhausted (no matching venues)
- **Solution**: Increase `min_samples` or add more training data

**Issue**: Corrections too extreme
- **Check**: Shrinkage parameter `k`
- **Solution**: Increase `k` to apply more shrinkage

## Roadmap

**v1.1 (planned):**
- Multi-market joint estimation (PRA → decompose to PTS + REB + AST)
- Temporal decay (recent games weighted higher)
- Player-specific corrections (superstar vs role player)

**v1.2 (planned):**
- Online learning (incremental updates without full retrain)
- Confidence intervals via bootstrap
- A/B testing framework for production

## References

- Shrinkage estimation: James-Stein estimator, Empirical Bayes
- Categorical hashing: Feature hashing (Weinberger et al.)
- Time-based validation: Proper backtest methodology (no lookahead bias)
