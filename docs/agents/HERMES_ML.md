# Hermes playbook — Track F ML pipeline (advisory)

Offline research ML path: features → train → temperature calibrate → EV annotate →
`MODEL_PROBABILITY_EDGE`. **No real money. No book placement.**

## Freeze (v0.5.0 after Track G)

Field-test at tag **`v0.5.0-advisory-beta`** once cut (Track F + G).  
Checklist: [TRACK_F_FREEZE_AND_FIELD_TEST.md](../TRACK_F_FREEZE_AND_FIELD_TEST.md).  
Track G presets: [TRACK_F_FUTURE_TRANSFORMERS.md](../TRACK_F_FUTURE_TRANSFORMERS.md).

```bash
# Larger / dist models (optional torch)
make ml-axial-train-large
make ml-axial-train-transformer   # includes distributional CRPS head
```

## Commands

```bash
cd "$(git rev-parse --show-toplevel)"
# Prefer project venv
source .venv/bin/activate 2>/dev/null || true

# Full E2E: train day001+day002, apply day003, assert model-edge candidates
make ml-e2e

# Annotate + compete on a fixture day (explicit model-edge opt-in)
python scripts/holler/ml_compete_day.py \
  --fixture-day fixtures/day003 \
  --train-days fixtures/day001 fixtures/day002 \
  --allow-model-edge \
  --out-dir data/ml/compete
```

### API (operator)

```bash
make api   # uvicorn :8000

curl -s -X POST localhost:8000/v1/ml/train \
  -H 'content-type: application/json' \
  -d '{"train_fixtures":["day001","day002"]}' | jq .

curl -s -X POST localhost:8000/v1/runs/ingest \
  -H 'content-type: application/json' \
  -d '{"fixture":"day003"}' | jq .status

curl -s -X POST localhost:8000/v1/ml/annotate \
  -H 'content-type: application/json' \
  -d '{"auto_compete":true,"allow_forecast_weighting":true,"reliability_status":"RELIABLE"}' | jq .

curl -s localhost:8000/v1/ml/status | jq .

# Advisory retrain proposal (never auto-trains)
curl -s -X POST localhost:8000/v1/ml/retrain-check \
  -H 'content-type: application/json' \
  -d '{"eval_fixtures":["day001","day002","day003"]}' | jq .
```

Workbench: **Health → Research ML (Track F)** — Train / Annotate+compete / Retrain check.

### Model cards

```bash
make ml-train
make ml-doc-model   # or auto-written under data/ml/model_cards/ on train
curl -s localhost:8000/v1/ml/model-card | jq '{model_id, metrics, packet_hash}'
```

### Axial model (PyTorch + stdlib stub)

```bash
# Optional install (CPU wheels fine for research)
pip install -e "packages/hollersports[torch]"

# Train axial on fixtures
make ml-axial-train
# or: python scripts/holler/train_axial.py fixtures/day001 fixtures/day002 --out-dir data/ml/axial

curl -s -X POST localhost:8000/v1/ml/axial/train \
  -H 'content-type: application/json' \
  -d '{"train_fixtures":["day001","day002","day003"],"epochs":40}' | jq .

# Score last ingest: auto prefers trained torch, else stub
curl -s -X POST localhost:8000/v1/ml/axial \
  -H 'content-type: application/json' \
  -d '{"backend":"auto"}' | jq '{status,backend,kind,probability,trained}'

# Force stdlib stub (no torch)
curl -s -X POST localhost:8000/v1/ml/axial-stub | jq .
```

### RSS sentiment (optional network)

```bash
# CI / offline inject
python scripts/holler/fetch_rss_sentiment.py \
  --xml-file /path/to/feed.xml \
  --markets-json fixtures/day003/odds_records.json \
  --out data/ml/rss_sentiment.last.json

# Live ESPN sports RSS (opt-in network)
python scripts/holler/fetch_rss_sentiment.py --fetch --markets-json fixtures/day003/odds_records.json

curl -s -X POST localhost:8000/v1/ml/sentiment/rss \
  -H 'content-type: application/json' \
  -d '{"feed_xml":"<?xml ...>","fetch":false}' | jq .
# Live: {"fetch":true}  (HTTPS, cached under data/http_cache)
```

### Retrain check (advisory only)

```bash
# After train: evaluate Brier vs stored baseline; may emit RETRAIN_SUGGESTED
make ml-train
make ml-retrain-check
# → docs/evidence/ml_retrain_proposal.last.json
# Never auto-trains. Hermes may surface suggested_command for human approval.

# After review, optional gated apply (confirm required):
curl -s -X POST localhost:8000/v1/ml/retrain-apply \
  -H 'content-type: application/json' \
  -d '{"confirm":true,"require_suggestion":true,"train_fixtures":["day001","day002","day003"]}' | jq .
```

### Odds movement (free-first)

- Cross-book: multi-book Odds API lines get `odds_history`, `odds_delta`, `book_dispersion`
- Temporal: re-observe writes/reads `data/ml/odds_implied_snapshots.json` (via API `data_root` or CLI `--data-root`)
- Features consume `odds_delta` (never invents prices)

Stepwise:

```bash
python scripts/holler/build_features.py fixtures/day001 fixtures/day002 --require-labels
python scripts/holler/train_gbm.py fixtures/day001 fixtures/day002 --out-dir data/ml
python scripts/holler/apply_model.py \
  --odds fixtures/day003/odds_records.json \
  --ensemble data/ml/ensemble.json \
  --out data/ml/day003_annotated.json \
  --emit-candidates
```

Optional sklearn trainer (not required for CI):

```bash
pip install -e "packages/hollersports[ml]"
python scripts/holler/train_gbm.py fixtures/day001 fixtures/day002 --sklearn --out-dir data/ml
```

## Laws

1. `capital_authority` / `execution_authority` always false  
2. No ensemble file → fail closed (do not invent `model_probability`)  
3. Production Workbench still gates model edge via calibration ladder;  
   `--allow-model-edge` is **offline demo only**  
4. Prefer fixtures; live free-first is a separate track  

## Design

- Spec: `docs/superpowers/specs/2026-08-05-hollersports-ml-pipeline-design.md`
- Research notes: `docs/arxiv_research_summary.md`
- Package: `packages/hollersports/hollersports/ml/`

## Evidence

- `docs/evidence/ml_pipeline_e2e.last.json` after `make ml-e2e`
