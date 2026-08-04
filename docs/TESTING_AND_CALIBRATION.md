# Testing framework & calibration

Advisory only — **no real money**, **no book placement**.

## Test layout

| Layer | Path | Marker | Purpose |
|-------|------|--------|---------|
| Unit | `tests/unit/` | `unit` | Pure functions, strategies, gates |
| Integration | `tests/integration/` | `integration` | FastAPI + fixture loops |
| Golden | `tests/golden/` | `golden` | Determinism, authority locks |
| Calibration | `tests/calibration/` + unit cal tests | `calibration` | Evidence ladder + model-edge matrix |

Shared fixtures: `tests/conftest.py` (`fixture_day001`, `fixture_day002`, settled samples).

## Commands

```bash
# Full package suite (CI default)
make test
# or: pytest tests/ --ignore=hollersports-core

# By layer
make test-unit
make test-integration
make test-golden
make test-calibration

# Coverage (terminal report)
make test-cov

# Smoke + multi-fixture calibration receipt
make smoke
make calibration-suite
```

## Calibration ladder

Module: `hollersports.runes.calibration_evaluator.evaluate_calibration`

| Status | Meaning |
|--------|---------|
| `EMPTY` | No settled paper rows |
| `UNRELIABLE` | Below watch sample floor |
| `WATCH` | Enough for watch; not reliable |
| `RELIABLE` | Sample + hit_rate + sim_roi floors pass |

Default floors (sim metrics only):

| Threshold | Default |
|-----------|---------|
| `min_sample_watch` | 5 |
| `min_sample_reliable` | 20 |
| `min_hit_rate_reliable` | 0.45 |
| `min_sim_roi_reliable` | −0.15 |

**Model edge** requires:

1. `allow_forecast_weighting=true` (operator opt-in), and  
2. `reliability_status == RELIABLE` (from ladder or manual override).

Gate: `calibration_allows_model_edge` · strategy: `MODEL_PROBABILITY_EDGE`.

### API

```bash
# Evidence packet from last settlements
curl -s 'localhost:8000/v1/calibration?allow_forecast_weighting=1' | jq .

# Compete with auto ladder (recommended)
curl -s -X POST localhost:8000/v1/runs/compete \
  -H 'content-type: application/json' \
  -d '{"allow_forecast_weighting":true,"use_auto_calibration":true}' | jq '.model_edge_enabled'

# Manual RELIABLE override (tests / explicit operator override)
curl -s -X POST localhost:8000/v1/runs/compete \
  -H 'content-type: application/json' \
  -d '{"allow_forecast_weighting":true,"reliability_status":"RELIABLE","use_auto_calibration":false}' | jq '.model_edge_enabled'
```

Workbench: **Health → Calibration** shows ladder; **Today** checkbox uses auto-calibration when allowing model edge.

## CI

`.github/workflows/ci.yml`:

1. `pytest tests/ --ignore=hollersports-core` (all layers)  
2. `scripts/smoke_operator_day.py`  
3. `scripts/run_calibration_suite.py`  
4. operator-web build + live-UX string guard  

## Product law

Calibration and tests measure **advice quality** only. They never set `capital_authority` or `execution_authority` true.
