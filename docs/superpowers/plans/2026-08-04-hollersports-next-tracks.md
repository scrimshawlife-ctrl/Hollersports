# HollerSports — next tracks (post advisory beta)

> After PR #3 merge to `main` (**MERGED** `838ea88`). Continuum tip `42ca274`.  
> Advisory only — no real money. **No open PR** — work lands on `main`.

## Completed (v0.2 → v0.3 advisory beta)

Tasks 1–9 of standalone operator plan + readiness board + CI + smoke.  
Primary package, FastAPI, Cobalt Workbench, goldens, advisory contract.  
Post-merge continuum: free-first, model edge, calibration ladder, settlement bank, Hermes backfill docs.

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

## Track D — Packaging / release

- [x] Tag `v0.3.0-advisory-beta` (when cut)
- Optional PyPI private publish later
- Legacy `engine/` relocation only if consumers need it ([MIGRATION_ENGINE.md](../../MIGRATION_ENGINE.md))

## Hard constraints (all tracks)

- No wallets, payments, book placement, capital custody  
- `capital_authority` / `execution_authority` always false  
- Fail closed on missing odds/provenance  
