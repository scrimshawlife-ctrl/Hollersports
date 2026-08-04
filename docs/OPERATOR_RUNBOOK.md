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

Closed path available **through paper ledger** (ingest → compete → paper).  
Settlement / promotion / FastAPI / Next.js operator UI are design-specified and planned; land them before treating the full day loop as shipped.

### Programmatic paper path

```python
from pathlib import Path
from hollersports.sources.fixture_adapter import load_fixture_day
from hollersports.pipelines.market_ingestion import run_market_ingestion
from hollersports.pipelines.strategy_competition import run_strategy_competition
from hollersports.pipelines.paper_loop import run_paper_loop

day = load_fixture_day(Path("fixtures/day001"))
ingest = run_market_ingestion(day["ingest_payload"])
assert ingest["status"] == "INGESTED"

comp = run_strategy_competition(ingest)
assert comp["status"] == "COMPUTED"

# paper first N candidates under all-true fixture gates
candidates = comp.get("candidates", [])[:5]
context = {
    "run_id": ingest.get("run_id", "FIX-DAY001"),
    "price": 1.91,
    "bankroll": 1000.0,
    "human_max_stake": 25.0,
    "gates": {
        "source_health_gate": True,
        "governance_gate": True,
        "truth_gate": True,
        "liquidity_gate": True,
        "bankroll_gate": True,
    },
}
# Prefer per-candidate paper via run_execution_guard + ledger; see paper_loop
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
