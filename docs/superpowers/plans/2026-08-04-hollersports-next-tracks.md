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
- [ ] Optional: HTTP response cache / backoff polish
- [ ] Optional: API route `POST /v1/runs/free-first` (Workbench button)

## Track B — Workbench polish

- Persist candidates in API session/store so Book select matches UI selection (not only server top-N)
- Empty/loading/error states audit on Today/Book/Health
- One-click “run full fixture day” button → operator_day

## Track C — Advice quality loop

- Nightly fixture/backfill job docs
- Reliability buckets by league/market after more settlements
- Keep promotion **advisory review only** (never money)

## Track D — Packaging / release

- Tag `v0.3.0-advisory-beta`
- Optional PyPI private publish later
- Legacy `engine/` relocation only if consumers need it ([MIGRATION_ENGINE.md](../../MIGRATION_ENGINE.md))

## Hard constraints (all tracks)

- No wallets, payments, book placement, capital custody  
- `capital_authority` / `execution_authority` always false  
- Fail closed on missing odds/provenance  
