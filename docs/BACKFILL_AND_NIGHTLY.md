# Backfill and nightly advice-quality jobs

Advisory only — **no real money**, **no book placement**.

## Purpose

Accumulate settled paper simulations so reliability buckets and promotion review
have sample size. This is **advice calibration**, not P&L.

## Fixture backfill (offline / CI-safe)

```bash
cd Hollersports
python3 -m venv .venv && source .venv/bin/activate
pip install -e "packages/hollersports[dev]"

# Repeatable operator day → smoke receipt
python scripts/smoke_operator_day.py --out docs/evidence/smoke_operator_day.last.json

# Or API
# make api  then: curl -X POST localhost:8000/v1/runs/full-day -H 'content-type: application/json' -d '{"fixture":"day001"}'
```

## Optional live free-first observation

```bash
# ESPN only
python scripts/holler_free_first_ingest.py --espn-only --out out/free_first.json

# ESPN + Odds API
export THE_ODDS_API_KEY=...
python scripts/holler_free_first_ingest.py --out out/free_first.json
```

Workbench: **Free-first live observe** on Today (may hit network; fail-closed if offline).

## Suggested cron (operator machine)

```cron
# Nightly fixture sim (always offline-safe)
15 6 * * * cd /path/to/Hollersports && . .venv/bin/activate && python scripts/smoke_operator_day.py --out docs/evidence/smoke_operator_day.last.json >> out/nightly.log 2>&1

# Optional: live observe weekdays (requires network; never places bets)
30 6 * * 1-5 cd /path/to/Hollersports && . .venv/bin/activate && python scripts/holler_free_first_ingest.py --espn-only --out out/free_first_$(date +\%Y\%m\%d).json >> out/nightly.log 2>&1
```

## Reliability review

After settlements exist in the API store:

```bash
curl -s localhost:8000/v1/reliability | jq .
# Append-only snapshots after each settle
curl -s 'localhost:8000/v1/reliability?history=1&limit=20' | jq .
```

Or open Workbench **Health → Advice reliability** and **Reliability history**.

Promotion stays **BLOCKED** until design gates (sample size, ROI, etc.) pass — still
**review only**, never money.

## Hard rules

- Do not schedule any script that places bets or moves capital (none exist).
- Do not commit API keys.
- Prefer fixtures for CI and demos.
