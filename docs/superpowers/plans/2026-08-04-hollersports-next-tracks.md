# HollerSports — next tracks (post advisory beta)

> After PR #3 merge to `main` (**MERGED** `838ea88`).  
> **Freeze for field test:** tag **`v0.5.0-advisory-beta`** (package 0.5.0) — Track F + G complete.  
> See [TRACK_F_FREEZE_AND_FIELD_TEST.md](../../TRACK_F_FREEZE_AND_FIELD_TEST.md).  
> Advisory only — no real money.

## Completed (v0.2 → v0.3 advisory beta)

Tasks 1–9 of standalone operator plan + readiness board + CI + smoke.  
Primary package, FastAPI, Cobalt Workbench, goldens, advisory contract.  
Post-merge continuum: free-first, model edge, calibration ladder, settlement bank, Hermes backfill docs.

## Completed (v0.4 Track F — frozen for testing)

Research ML pipeline (#12–#17): features → train → EV → annotate; odds movement;  
sentiment + RSS; model cards; axial stub + optional PyTorch; gated retrain.  
**Do not expand model capacity until unfreeze** ([TRACK_F_FUTURE_TRANSFORMERS.md](../../TRACK_F_FUTURE_TRANSFORMERS.md)).

## Track A — Free-first live ingest (optional keys)

**Goal:** Optional live schedule/odds adapters behind source registry; fixture remains default and CI path.

- [x] ESPN scoreboard normalize + optional fetch
- [x] The Odds API normalize + fetch when `THE_ODDS_API_KEY` set
- [x] Source conflict packet (`SourceConflictPacket.v1`)
- [x] `build_live_observation_pack` + `scripts/holler_free_first_ingest.py` + `make free-first`
- [x] Tests: injected raw / monkeypatch; never require keys in CI
- [x] HTTP response cache (file TTL) for ESPN/Odds fetches
- [x] API route `POST /v1/runs/free-first` + Workbench button

## Track B — Workbench polish

- [x] `GET /v1/candidates` + `POST /v1/runs/full-day`
- [x] Paper accepts optional `candidate_ids` (UI selection → sim)
- [x] Today: one-click “Run full fixture day”
- [x] Health loading/error/empty copy + advisory banner
- [x] Free-first live observe button (network optional; fail-closed)

## Track C — Advice quality loop

- [x] Reliability buckets by strategy / league / market_type
- [x] `GET /v1/reliability` + Health “Advice reliability” table
- [x] Nightly fixture/backfill job docs (`docs/BACKFILL_AND_NIGHTLY.md`)
- [x] Gated `MODEL_PROBABILITY_EDGE` (deterministic package-native; calibration on)
- [x] Append-only reliability history ledger + `GET /v1/reliability?history=1`
- [x] Workbench Health “Reliability history” table + release notes
- [x] Compete calibration body + Today toggle; fixture `day002` (model fields)
- Keep promotion **advisory review only** (never money)

## Track E — Local operator polish (post Vercel deferral)

Original local-first path (no hosted SaaS). Continue here:

- [x] Second fixture day for multi-day / model-edge demos
- [x] Operator-visible model-edge calibration gate (default off)
- [x] Calibration evaluator ladder (EMPTY→UNRELIABLE→WATCH→RELIABLE)
- [x] Testing framework: markers, conftest, `make test-*`, calibration suite + CI
- [x] `GET /v1/calibration` + Health Calibration panel + auto-cal compete
- [x] Cumulative settlement history bank + `make backfill` multi-fixture accumulation
- [x] Multi-event fixture markets (full slate, not primary-only)
- [x] Fixture `day003` + Book model-edge chip / strategy family
- [x] Free-first live sport coverage expansion (day-one leagues via API/CLI/Workbench)
- [x] Free-first multi-ingest auto-compete (merge candidates across INGESTED events)
- [x] Persist free-first ingest slate for paper prices + re-compete
- [x] Free-first ESPN finals → settle (injected/opt-in fetch; PENDING if not final)
- [x] Workbench slate summary (ingest_count / competed_event_count)
- [x] Today Settle uses ESPN finals on free-first slate; Book settlement queue + re-settle
- [x] Settlement bank: calibration collapses latest terminal per `entry_id` (re-settle safe)
- [x] Headless free-first closed day CLI (`make free-first-day` / `scripts/free_first_operator_day.py`)
- [x] API `POST /v1/runs/free-first-day` + Workbench Today closed-day button

## Track D — Packaging / release

- [x] Tag `v0.3.0-advisory-beta` (when cut)
- [x] Tag `v0.4.0-advisory-beta` (Track F research ML on main)
- [x] Tag `v0.5.0-advisory-beta` (Track F + G freeze for field test)
- Optional PyPI private publish later
- Legacy `engine/` relocation only if consumers need it ([MIGRATION_ENGINE.md](../../MIGRATION_ENGINE.md))

## Track F — Research ML pipeline (CLI-only, arxiv slice)

Design: [`docs/superpowers/specs/2026-08-05-hollersports-ml-pipeline-design.md`](../specs/2026-08-05-hollersports-ml-pipeline-design.md)  
Source notes: [`docs/arxiv_research_summary.md`](../../arxiv_research_summary.md)

- [x] Feature builder from fixture markets (implied p, consensus, public, clv; odds-Δ/sentiment stubs)
- [x] Baseline trainer (pure-Python L2 logistic; optional sklearn HGB via `[ml]`)
- [x] Temperature calibration + ensemble artifact
- [x] Small-n temperature guard (identity T until val bank ≥ 8; cap T ≤ 2.5)
- [x] EV annotate → `model_probability` for existing `MODEL_PROBABILITY_EDGE`
- [x] CLIs under `scripts/holler/` + `make ml-e2e` (asserts candidates ≥ 1)
- [x] `make ml-compete` — annotate fixture day + compete with explicit model-edge opt-in
- [x] Hermes playbook `docs/agents/HERMES_ML.md`
- [x] API `GET/POST /v1/ml/{status,train,annotate}` + Health Workbench panel
- [x] Free-first odds movement: cross-book `odds_history`/`odds_delta` + temporal snapshots under `data/ml/`
- [x] Hermes retrain evaluator (advisory proposal only; `make ml-retrain-check`; never auto-trains)
- [x] API `POST /v1/ml/retrain-check` + Health “Retrain check” button
- [x] Offline sentiment lexicon (headline/snippet → `sentiment_score`; no network)
- [x] Model cards (`scripts/holler/doc_model.py`, auto on train, `GET /v1/ml/model-card`)
- [x] Axial **stub** (stdlib dual-axis smooth; `POST /v1/ml/axial-stub`)
- [x] Real PyTorch axial model (`[torch]` extra; train + `POST /v1/ml/axial` auto/torch)
- [x] RSS sentiment feeds (inject XML / opt-in HTTPS; `POST /v1/ml/sentiment/rss`; lexicon match)
- [x] Gated retrain apply (`POST /v1/ml/retrain-apply` requires `confirm=true`; optional suggestion gate)
- [x] **Freeze** at `v0.4.0-advisory-beta` for small-scale field testing

## Track G — Temporal capacity (research scale — before freeze)

> Implemented for freeze **v0.5.0**. Details: [TRACK_F_FUTURE_TRANSFORMERS.md](../../TRACK_F_FUTURE_TRANSFORMERS.md).

- [x] G0: multi-poll sequence store + fixture sequences JSON  
- [x] G1: `axial_large` + `transformer` presets behind same train/score interface  
- [x] G2: `transformer_dist` total bins + CRPS metrics  
- [x] G3: RSS remains live text path (social firehose still out of scope)  
- [x] G4: model cards written on axial/transformer train  

**Field freeze after v0.5.0 tag:** see [TRACK_F_FREEZE_AND_FIELD_TEST.md](../../TRACK_F_FREEZE_AND_FIELD_TEST.md).

## Hard constraints (all tracks)

- No wallets, payments, book placement, capital custody  
- `capital_authority` / `execution_authority` always false  
- Fail closed on missing odds/provenance  
