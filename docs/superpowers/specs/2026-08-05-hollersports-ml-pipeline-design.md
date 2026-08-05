# HollerSports Track F — Research ML pipeline (CLI-only)

> Advisory only. No capital/execution authority. Fail closed on missing models.  
> **Shipped and frozen for field test** at `v0.4.0-advisory-beta`.  
> Future capacity: [TRACK_F_FUTURE_TRANSFORMERS.md](../../TRACK_F_FUTURE_TRANSFORMERS.md).

## Goal

Land the high-ROI slice from `docs/arxiv_research_summary.md` without live feeds or
axial transformers: **features → baseline train → temperature calibrate → EV annotate**,
feeding existing `MODEL_PROBABILITY_EDGE` via `model_probability` on markets.

## Non-goals (deferred)

- Live odds polling / sentiment APIs
- Axial transformer / PyTorch
- Full score distributions (CRPS)
- Hermes auto-retrain loop
- Workbench / API annotate routes

## Architecture

```
fixtures/day00N
  → build_features → features.jsonl
  → train_baseline → model artifact (JSON weights or optional sklearn joblib + sidecar)
  → ensemble_calibrate → ensemble artifact (weights + temperature T)
  → apply_model → annotated odds/markets JSON with model_probability + EV fields
  → existing ingest / compete / MODEL_PROBABILITY_EDGE (calibration gate unchanged)
```

## Components

| Module | Responsibility |
|--------|----------------|
| `hollersports.ml.features` | Implied p, market fields, label join; never invent odds |
| `hollersports.ml.train` | Pure-Python L2 logistic (default); optional sklearn HGB if `[ml]` installed |
| `hollersports.ml.calibrate` | Temperature scaling + single-model ensemble; identity T when val n < 8; cap T ≤ 2.5 |
| `hollersports.ml.ev` | EV = p_model × decimal − 1; advisory thresholds only |
| `hollersports.ml.apply` | Load ensemble, score rows, attach provenance + hash |
| `scripts/holler/*` | Thin CLIs over the package |

## Dependencies

- Default: stdlib only (no numpy/sklearn required for CI).
- Optional: `pip install -e "packages/hollersports[ml]"` → scikit-learn.

## Artifacts

- Runtime: `data/ml/` (gitignored)
- Tests: temp dirs only
- Provenance: `model_id`, `data_hash`, `artifact_hash`, `feature_names`, metrics

## Hard laws

1. `capital_authority` / `execution_authority` always false  
2. No model file → no invented `model_probability`  
3. Offline fixtures preferred  

## Success criteria

- `make test` green without sklearn  
- Train on day001+day002, apply on day003 → annotated markets with EV + provenance  
- `MODEL_PROBABILITY_EDGE` emits candidates when edge ≥ threshold on annotated markets  
