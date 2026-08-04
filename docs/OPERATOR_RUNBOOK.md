# Operator runbook

Paper-only operator day using fixtures. No live book placement.

## Prerequisites

- Python ≥ 3.11  
- Repo root as cwd for fixtures + schemas  

```bash
cd Hollersports
python3 -m venv .venv && source .venv/bin/activate
pip install -e "packages/hollersports[dev]"
pytest tests/ --ignore=hollersports-core -q
```

## Fixture day (current path)

Closed loop available via **`run_operator_day`**: ingest → compete → paper → settle → performance → promotion → dashboard projection.  
FastAPI + Next.js operator UI remain planned.

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

### Fixture location

`fixtures/day001/` — multi-league schedule + odds-shaped markets (NBA ML includes consensus / public / CLV feature fields).

## Live free sources

Optional adapters and API keys are **not required** for fixture mode.  
Document keys when live fetch is wired (`THE_ODDS_API_KEY`, etc.). Without keys, stay on fixtures.

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
