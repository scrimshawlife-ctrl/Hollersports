# Operator runbook

Advisory operator day using fixtures. **No real money. No live book placement.**  
Paper stakes/settlement measure **advice quality**, not payouts.

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
FastAPI + Next.js operator UI remain planned.

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

Today actions:

- **Run full fixture day** — offline-safe closed loop  
- **Free-first live observe** — optional network (ESPN; Odds if `THE_ODDS_API_KEY`); fail-closed if offline  

### Fixture location

`fixtures/day001/` — multi-league schedule + odds-shaped markets (NBA ML includes consensus / public / CLV feature fields).

## Live free sources (optional — Track A)

Fixture mode remains the **CI and default** path. Live observation is opt-in and still **advisory only** (no money, no book placement).

```bash
# ESPN scoreboard only (no API key)
make free-first
# or: python scripts/holler_free_first_ingest.py --espn-only --out out/free_first_observation.json

# ESPN + The Odds API when key present
export THE_ODDS_API_KEY=your_key
python scripts/holler_free_first_ingest.py --out out/free_first_observation.json
```

| Env | Purpose |
|-----|---------|
| `THE_ODDS_API_KEY` | Optional multi-book odds (The Odds API free tier) |

Without keys, odds side is skipped (`errors` list notes `THE_ODDS_API_KEY_not_set`).  
Output pack includes `espn_events`, `odds_events`, `conflict`, optional `ingest` packet.

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
