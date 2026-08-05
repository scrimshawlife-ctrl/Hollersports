# Track F freeze — test the small-scale ML stack

**Decision:** Freeze research ML scope at **`v0.4.0-advisory-beta`** (`hollersports` **0.4.0**, tip at/after tag `v0.4.0-advisory-beta`) for **operator field testing**.

Larger production transformers, social firehoses, and auto-Hermes retrain loops are **out of freeze scope**. Ship and learn on the small stack first.

---

## What is frozen (in scope for testing)

| Layer | What to exercise |
|-------|------------------|
| Offline ML | `make ml-e2e` — train day001+002 → annotate day003 → model-edge candidates |
| Operator API | `/v1/ml/train`, `/annotate`, `/status`, `/retrain-check`, `/retrain-apply` (confirm), `/model-card` |
| Axial | stdlib stub always; optional PyTorch small axial if `[torch]` installed |
| Odds movement | free-first re-observe snapshots under `data_root/ml/` |
| Sentiment | offline lexicon + RSS inject; optional `fetch=true` only if network OK |
| Workbench | Health → Research ML panel |
| Product law | `capital_authority` / `execution_authority` always false; no book placement |

Default CI path stays **`[dev]` only** (no torch/sklearn required).

---

## Explicit freeze criteria (met)

1. Track F checklist complete on `main` (see next-tracks Track F).  
2. Tag **`v0.4.0-advisory-beta`** cut; package version **0.4.0**.  
3. Small-scale path proven offline (`make ml-e2e`, unit/integration green).  
4. Gated retrain never silent (`confirm=true`).  
5. **No** claim that model quality is production-grade or money-ready.

---

## Field-test checklist (do this, not more model research)

```bash
cd "$(git rev-parse --show-toplevel)"
git checkout v0.4.0-advisory-beta   # or main at/after that tag
python3 -m venv .venv && source .venv/bin/activate
pip install -e "packages/hollersports[dev]"

# 1) Operator day (fixture)
make smoke
make backfill-status
make api    # terminal 1
make web    # terminal 2 — Today: day003 full day / paper / settle

# 2) Small-scale ML (offline)
make ml-e2e
# Expect: temperature identity or mild; ≥1 MODEL_PROBABILITY_EDGE candidates

# 3) API path
curl -s -X POST localhost:8000/v1/ml/train \
  -H 'content-type: application/json' \
  -d '{"train_fixtures":["day001","day002"]}' | jq '{status,model_id,metrics}'
curl -s -X POST localhost:8000/v1/runs/ingest \
  -H 'content-type: application/json' \
  -d '{"fixture":"day003"}' | jq .status
curl -s -X POST localhost:8000/v1/ml/annotate \
  -H 'content-type: application/json' \
  -d '{"auto_compete":true,"allow_forecast_weighting":true,"use_auto_calibration":true}' \
  | jq '{status,model_edge_enabled,model_edge_candidate_count}'

# 4) Calibration bank growth (advice quality, not model size)
make backfill
python scripts/backfill_status.py

# 5) Optional only if testing live observation (not required for freeze)
# make free-first   # needs network / optional THE_ODDS_API_KEY
```

**Pass signals for freeze testing:** smoke green; ml-e2e exit 0; Workbench loads; authorities never true; annotate does **not** force RELIABLE without evidence.

**Out of freeze test scope:** training huge transformers; live Twitter; money rails; PyPI.

---

## What we deliberately do **not** build until unfreeze

See [TRACK_F_FUTURE_TRANSFORMERS.md](TRACK_F_FUTURE_TRANSFORMERS.md).

| Deferred | Why wait |
|----------|----------|
| Production-scale axial / full transformers | Need dense sequential data + larger settled bank first |
| Social firehose (Twitter/X, etc.) | RSS is enough for freeze; auth/rate limits distract field tests |
| Auto-apply retrain without human/Hermes confirm | Product law: no silent model updates |
| Replacing logistic as CI default | Keep fail-closed, fast, deterministic CI |

---

## Unfreeze triggers (when to invest in larger models)

Unfreeze **only when most of these are true**:

1. **Calibration sample** — settlement bank regularly clears RELIABLE floors (sample + hit_rate + sim_roi), not just EMPTY/WATCH.  
2. **Sequential data** — free-first or fixtures store multi-poll / minute-level sequences (not only static day odds).  
3. **Stable small stack** — field issues from freeze testing are triaged; logistic/small axial not the bottleneck.  
4. **Measured gap** — held-out Brier/CRPS or paper EV plateaus on hand features; more capacity has a hypothesis, not a vibe.  
5. **Ops budget** — willingness to own `[torch]` (or GPU) as an optional research path, still gated for operator model edge.

Until then: **grow data and operator muscle, not model size.**

---

## Related docs

| Doc | Role |
|-----|------|
| [RELEASE_NOTES.md](RELEASE_NOTES.md) | `v0.4.0-advisory-beta` |
| [agents/HERMES_ML.md](agents/HERMES_ML.md) | ML operator playbook |
| [TRACK_F_FUTURE_TRANSFORMERS.md](TRACK_F_FUTURE_TRANSFORMERS.md) | Post-freeze transformer roadmap |
| [superpowers/plans/2026-08-04-hollersports-next-tracks.md](superpowers/plans/2026-08-04-hollersports-next-tracks.md) | Track F done; Track G deferred |
