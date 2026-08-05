# Operator runbook

Advisory operator day using fixtures. **No real money. No live book placement.**  
**Release freeze for testing:** package **0.5.0** · tag **`v0.5.0-advisory-beta`**  
(see [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md),  
[TRACK_F_FREEZE_AND_FIELD_TEST.md](TRACK_F_FREEZE_AND_FIELD_TEST.md)).  
Paper stakes/settlement measure **advice quality**, not payouts.

### Recommended field-test pin

```bash
git checkout v0.5.0-advisory-beta
pip install -e "packages/hollersports[dev]"
make smoke
make ml-e2e    # logistic ML path
make api       # + make web for Workbench
# optional torch: make ml-axial-train-transformer
```

## Prerequisites

- Python ≥ 3.11  
- Repo root as cwd for fixtures + schemas  
- Optional: Node 22+ for Workbench UI  

```bash
cd Hollersports
python3 -m venv .venv && source .venv/bin/activate
make validate   # install, pytest, smoke receipt → docs/evidence/smoke_operator_day.last.json
```

## Fixture day (current path)

Closed loop available via **`run_operator_day`**: ingest → compete → paper → settle → performance → promotion → dashboard projection.  
FastAPI (`make api`) and Cobalt Workbench (`make web`) are **shipped** — Today / Book / Health.

### One-command smoke

```bash
python scripts/smoke_operator_day.py --out docs/evidence/smoke_operator_day.last.json
```

### Programmatic full day

```python
from pathlib import Path
from hollersports.pipelines.operator_day import run_operator_day

out = run_operator_day(Path("fixtures/day001"), data_root=Path("data/demo-run"))
assert out["ingest"]["status"] == "INGESTED"
assert out["competition"]["status"] == "COMPUTED"
assert out["dashboard"]["authority"] == "PROJECTION_ONLY"
assert out["promotion"]["status"] in ("BLOCKED", "WATCH", "REVIEW_ELIGIBLE", "PROMOTION_RECOMMENDED")
# small fixture sample normally yields BLOCKED
print(out.keys())  # ingest, competition, paper, settlements, performance, promotion, dashboard
```

### API + Workbench

```bash
make api   # :8000
make web   # :3000 — Today → Run full fixture day (or Free-first live observe)
```

Today controls and **action board** (Hallmark Cobalt Workbench — [design.md](../design.md)):

| Control / group | Purpose |
|-----------------|---------|
| **Fixture** select | `day001` (default), `day002`, or `day003` (model fields on day002+) |
| **Allow model edge** | Opt-in forecast weighting; evidence ladder must be `RELIABLE` before model edge loads (still SHADOW_ONLY) |
| **Free-first leagues** | Day-one league filter (default all) |
| **Fixture day** group | Primary: **Run full {day}** · secondary: Ingest |
| **Free-first live** group | Primary: **Free-first closed day** · secondary: Live observe (network optional) |
| **Paper loop** group | Primary: **Compete** · Paper top-N · Settle |

Health:

- **Anchors + panels** — ML · sources · performance · promotion · calibration · reliability · history · run log  
- **Calibration** — ladder status, sample, hit_rate, sim_roi, model_edge_allowed  
- **Research ML** — train / annotate+compete / retrain check (advisory only)

### Fixture location

| Day | Notes |
|-----|--------|
| `fixtures/day001/` | Multi-league schedule + odds-shaped markets (NBA ML includes consensus / public / CLV) |
| `fixtures/day002/` | Second slate; markets may include `model_probability` for gated model-edge demos |
| `fixtures/day003/` | Third slate for multi-day backfill / calibration sample growth + model fields |

Compete with model edge (API):

```bash
curl -s -X POST localhost:8000/v1/runs/compete \
  -H 'content-type: application/json' \
  -d '{"allow_forecast_weighting":true,"reliability_status":"RELIABLE"}' | jq '.model_edge_enabled,.candidate_count'
```

## Live free sources (optional — Track A)

Fixture mode remains the **CI and default** path. Live observation is opt-in and still **advisory only** (no money, no book placement).

```bash
# ESPN scoreboard only (no API key) — all day-one leagues
make free-first
# or: python scripts/holler_free_first_ingest.py --espn-only --out out/free_first_observation.json

# Single / subset leagues
python scripts/holler_free_first_ingest.py --espn-only --leagues NBA,NFL --out out/free_first_nba_nfl.json

# ESPN + The Odds API when key present
export THE_ODDS_API_KEY=your_key
python scripts/holler_free_first_ingest.py --out out/free_first_observation.json
```

| Env | Purpose |
|-----|---------|
| `THE_ODDS_API_KEY` | Optional multi-book odds (The Odds API free tier) |

Without keys, odds side is skipped (`errors` list notes `THE_ODDS_API_KEY_not_set`).  
Output pack includes `espn_events`, `odds_events`, `conflict`, optional `ingest` packet.

Closed day (observe → compete → paper → ESPN settle → calibration bank):

```bash
# Injected (CI-safe)
python scripts/free_first_operator_day.py --espn-raw … --odds-raw … --settle-espn-raw … --leagues NBA

# Live finals (network; never places bets)
make free-first-day
# API: POST /v1/runs/free-first-day  ·  Workbench Today → “Free-first closed day”
```

## Authority checks

Every packet must keep:

- `capital_authority: false`  
- `execution_authority: false`  
- execution path `mode: PAPER_ONLY`  

There is **no Place bet** control in product scope.

## Related

- [SYSTEM_CONTRACT.md](SYSTEM_CONTRACT.md)  
- [Atlas](atlas/HOLLERSPORTS_ATLAS.md)  
- [Design](superpowers/specs/2026-08-04-hollersports-standalone-design.md)  
- [Implementation plan](superpowers/plans/2026-08-04-hollersports-standalone-operator.md)  
