# HollerSports Atlas

Topology card for the standalone operator repository.  
Vocabulary: **OBSERVED** (in tree now) · **PLANNED** (design + plan) · **NOT_COMPUTABLE** (missing evidence).

## Identity

| | |
|--|--|
| **What it is** | Sports **betting advisory** operator: free-first / fixture ingest → market-first candidates → paper simulation to rank advice — fail-closed. |
| **What it is not** | Money handler, sportsbook, payment rail, live bet placer, or Abraxas runtime dependency. |
| **Package** | `hollersports` **0.3.0** (`packages/hollersports`) |
| **Mode** | `ADVISORY_ONLY` / `PAPER_ONLY` (sim) · `capital_authority=false` · `execution_authority=false` · **no real money** |
| **Main tip (docs pin)** | `aa89903` · foundation PR **#3** MERGED `838ea88` |
| **Evidence** | `README.md`, `docs/SYSTEM_CONTRACT.md`, `packages/hollersports/`, `schemas/json/`, `tests/`, `docs/agents/` |

## Surfaces

### Governance kernel — OBSERVED

| | |
|--|--|
| **What it is** | Authority enum, live-capital asserts, fail-closed packet builder, calibration gate helper, deterministic hashing. |
| **What it is not** | Execution or promotion authority. |
| **Paths** | `hollersports/governance/`, `hollersports/schemas/hashing.py` |
| **Tests** | `tests/unit/test_governance.py` |

### Packet contracts — OBSERVED

| | |
|--|--|
| **What it is** | Nine v1 JSON Schemas + Pydantic models + `validate_packet`. |
| **What it is not** | Runtime that invents missing fields. |
| **Paths** | `schemas/json/*.v1.schema.json`, `hollersports/schemas/packets.py`, `validate.py` |
| **Tests** | `tests/unit/test_packets.py` |

### Source health + fixture + free-first live ingest — OBSERVED

| | |
|--|--|
| **What it is** | Registry, fixture day packs (`day001`, `day002`, `day003`), source health, market ingestion; optional ESPN + Odds API observation pack + conflict detector. |
| **What it is not** | Recommendation engine or money path; live network never required for CI. |
| **Paths** | `hollersports/sources/`, `fixtures/day001/`, `fixtures/day002/`, `fixtures/day003/`, `fixtures/MANIFEST.json`, `scripts/holler_free_first_ingest.py` |
| **Tests** | `test_source_health`, `test_market_ingestion`, `test_espn_scoreboard`, `test_odds_api`, `test_source_conflict`, `test_free_first_ingest` |

### Strategy competition + model edge — OBSERVED

| | |
|--|--|
| **What it is** | Market-first strategies (consensus, public fade, CLV) + gated `MODEL_PROBABILITY_EDGE` (calibration + market fields). |
| **What it is not** | Execution or stake sizing; inventing model probs. |
| **Paths** | `hollersports/strategies/`, `pipelines/strategy_competition.py`, `runes/calibration_evaluator.py` |
| **Tests** | `test_strategy_*`, `test_model_edge`, `test_calibration_*` |

### Paper execution + ledgers — OBSERVED

| | |
|--|--|
| **What it is** | Execution guard (`PAPER_ONLY`), paper loop, hash-chained paper ledger, reliability history, **cumulative settlement bank**. |
| **What it is not** | Live books or capital authority. |
| **Paths** | `hollersports/paper/` (`ledger`, `reliability_ledger`, `settlement_history`), `pipelines/paper_loop.py` |
| **Tests** | `test_paper_ledger`, `test_reliability_*`, `test_settlement_history` |

### Settlement / performance / promotion / operator day — OBSERVED

| | |
|--|--|
| **What it is** | Settle entries, performance, promotion (review only), PROJECTION_ONLY dashboard, `run_operator_day`. |
| **What it is not** | Live capital or auto-promotion to live books. |
| **Paths** | `runes/settlement_engine.py`, `performance_tracker.py`, `promotion_evaluator.py`, `operator_project.py`, `pipelines/operator_day.py` |
| **Tests** | `test_settlement`, `test_performance_promotion`, `test_operator_day_fixture` |

### FastAPI packet API — OBSERVED

| | |
|--|--|
| **What it is** | `/v1/runs/*`, dashboard, portfolio, promotion, reliability (+ history), **calibration**, candidates, free-first, full-day. |
| **Paths** | `hollersports/api/` |
| **Tests** | `tests/integration/test_api.py` |

### Operator web (Workbench / Cobalt) — OBSERVED

| | |
|--|--|
| **What it is** | Next.js local dashboard: Today · Book · Health (calibration + reliability history). |
| **What it is not** | Place-bet UI. |
| **Paths** | `packages/operator-web/` |

### Testing + backfill + Hermes — OBSERVED

| | |
|--|--|
| **What it is** | Layered pytest (unit/integration/golden/calibration), smoke + calibration suite + backfill, agent playbooks. |
| **Paths** | `tests/`, `scripts/backfill_status.py`, `scripts/backfill_fixtures.py`, `docs/agents/`, `AGENTS.md` |
| **Commands** | `make test`, `make backfill-status`, `make backfill` |

### Legacy engine / feedback core — OBSERVED (legacy)

| | |
|--|--|
| **What it is** | Original slate isolation + feedback loop packages kept during migration. |
| **What it is not** | Primary operator path. |
| **Paths** | `engine/`, `hollersports-core/`, `INTEGRATION_GUIDE.md` |
| **Notes** | [MIGRATION_ENGINE.md](../MIGRATION_ENGINE.md) |

## Repository map

```text
Hollersports/
├── AGENTS.md                    # Agent entry (Hermes backfill)
├── packages/hollersports/       # Primary Python package (v0.3.0)
├── packages/operator-web/       # Cobalt Workbench
├── schemas/json/                # Canonical packet contracts
├── fixtures/day001|day002|day003/  # Offline multi-league day packs
├── fixtures/MANIFEST.json       # Fixture inventory for agents
├── tests/{unit,integration,golden,calibration}/
├── scripts/                     # smoke, calibration suite, backfill*
├── docs/
│   ├── agents/HERMES_BACKFILL.md
│   ├── atlas/HOLLERSPORTS_ATLAS.md
│   ├── SYSTEM_CONTRACT.md
│   ├── PRODUCTION_READINESS.md
│   ├── TESTING_AND_CALIBRATION.md
│   └── evidence/                # Smoke + readiness pins
├── engine/                      # Legacy
├── hollersports-core/           # Legacy
└── README.md
```

## PLANNED (not claimed)

- Hosted multi-tenant SaaS / Vercel production deploy  
- PyPI publish  
- Full Monte Carlo operator default  

## Related

- [SYSTEM_CONTRACT.md](../SYSTEM_CONTRACT.md)  
- [PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md)  
- [RELEASE_NOTES.md](../RELEASE_NOTES.md)  
- [agents/HERMES_BACKFILL.md](../agents/HERMES_BACKFILL.md)  
