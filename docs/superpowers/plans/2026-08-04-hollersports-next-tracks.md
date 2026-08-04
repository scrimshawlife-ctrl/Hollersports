# HollerSports — next tracks (post advisory beta)

> After PR #3 merge to `main`. Advisory only — no real money.

## Completed (v0.2 advisory beta)

Tasks 1–9 of standalone operator plan + readiness board + CI + smoke.  
Primary package, FastAPI, Cobalt Workbench, goldens, advisory contract.

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
- Keep promotion **advisory review only** (never money)

## Track D — Packaging / release

- [x] Tag `v0.3.0-advisory-beta` (when cut)
- Optional PyPI private publish later
- Legacy `engine/` relocation only if consumers need it ([MIGRATION_ENGINE.md](../../MIGRATION_ENGINE.md))

## Hard constraints (all tracks)

- No wallets, payments, book placement, capital custody  
- `capital_authority` / `execution_authority` always false  
- Fail closed on missing odds/provenance  
