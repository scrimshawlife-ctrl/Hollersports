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
| **Evidence** | `README.md`, `docs/SYSTEM_CONTRACT.md`, `packages/hollersports/`, `schemas/json/`, `tests/unit/` |

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
| **What it is** | Registry, fixture day pack, source health, market ingestion; optional ESPN + Odds API observation pack + conflict detector. |
| **What it is not** | Recommendation engine or money path; live network never required for CI. |
| **Paths** | `hollersports/sources/` (`espn_scoreboard`, `odds_api`, `source_conflict`, `free_first_ingest`), `runes/source_health.py`, `pipelines/market_ingestion.py`, `fixtures/day001/`, `scripts/holler_free_first_ingest.py` |
| **Tests** | `test_source_health`, `test_market_ingestion`, `test_espn_scoreboard`, `test_odds_api`, `test_source_conflict`, `test_free_first_ingest` |

### Strategy competition — OBSERVED

| | |
|--|--|
| **What it is** | Market-first strategies (consensus, public fade, CLV) + gated-off model edge + competition loop. |
| **What it is not** | Execution or stake sizing. |
| **Paths** | `hollersports/strategies/`, `hollersports/pipelines/strategy_competition.py` |
| **Tests** | `tests/unit/test_strategy_registry.py`, `test_strategy_competition.py` |

### Paper execution + ledger — OBSERVED

| | |
|--|--|
| **What it is** | Execution guard (`PAPER_ONLY`), stake sizer, bet construct, portfolio simulator, append-only hash-chained paper ledger, paper loop. |
| **What it is not** | Live books or capital authority. |
| **Paths** | `hollersports/runes/execution_guard.py`, `stake_sizer.py`, `bet_construct.py`, `portfolio_simulator.py`, `hollersports/paper/`, `pipelines/paper_loop.py` |
| **Tests** | `tests/unit/test_execution_guard.py`, `test_paper_ledger.py` |

### Settlement / performance / promotion / operator day — OBSERVED

| | |
|--|--|
| **What it is** | Settle entries, performance (excludes PENDING), promotion gates (§8.2), PROJECTION_ONLY dashboard, full fixture `run_operator_day`. |
| **What it is not** | Live capital or auto-promotion to live books. |
| **Paths** | `runes/settlement_engine.py`, `performance_tracker.py`, `promotion_evaluator.py`, `operator_project.py`, `pipelines/operator_day.py`, `fixtures/day001/results.json` |
| **Tests** | `tests/unit/test_settlement.py`, `test_performance_promotion.py`, `tests/integration/test_operator_day_fixture.py` |

### Golden invariance / authority locks — OBSERVED

| | |
|--|--|
| **What it is** | 12-run fixture invariance + authority lock goldens. |
| **Paths** | `tests/golden/` |

### FastAPI packet API — OBSERVED

| | |
|--|--|
| **What it is** | `/v1/runs/*`, `/v1/dashboard`, `/v1/portfolio`, `/v1/promotion` |
| **Paths** | `hollersports/api/` |
| **Tests** | `tests/integration/test_api.py` |

### Operator web (Workbench / Cobalt) — OBSERVED

| | |
|--|--|
| **What it is** | Next.js local dashboard: Today · Book · Health; Hallmark Workbench + Cobalt + N3 + Ft4. |
| **What it is not** | Place-bet UI. |
| **Paths** | `packages/operator-web/` |

### Legacy engine / feedback core — OBSERVED (legacy)

| | |
|--|--|
| **What it is** | Original slate isolation + feedback loop packages kept during migration. |
| **What it is not** | Primary operator path going forward. |
| **Paths** | `engine/`, `hollersports-core/`, `INTEGRATION_GUIDE.md` |

## Repository map

```text
Hollersports/
├── packages/hollersports/     # Primary Python package (v0.2)
├── schemas/json/              # Canonical packet contracts
├── fixtures/day001/           # Offline multi-league day pack
├── tests/unit/                # TDD unit suite (primary)
├── docs/
│   ├── atlas/HOLLERSPORTS_ATLAS.md
│   ├── SYSTEM_CONTRACT.md
│   ├── ABRAXAS_LINEAGE.md
│   ├── OPERATOR_RUNBOOK.md
│   ├── images/hollersports-hero.jpg
│   └── superpowers/           # Design + implementation plan
├── engine/                    # Legacy slate engine
├── hollersports-core/         # Legacy feedback loop
└── README.md
```

## Pipeline

```text
fixtures | free sources
    → source_health
    → MarketIngestionPacket
    → strategy competition (SHADOW_ONLY candidates)
    → execution_guard (PAPER_ONLY)
    → paper ledger
    → settle → performance → promotion → dashboard projection  [library OBSERVED]
    → FastAPI /v1 + Workbench UI                               [OBSERVED local]
```

## Governance seals

```text
REAL_MONEY=false
CAPITAL_AUTHORITY=false
EXECUTION_AUTHORITY=false
LIVE_BOOKS=false
ABRAXAS_RUNTIME_REQUIRED=false
MODE=PAPER_ONLY   # simulation of advice quality, not funds
PURPOSE=ADVISORY_ONLY
```

## Related docs

| Doc | Role |
|-----|------|
| [SYSTEM_CONTRACT.md](../SYSTEM_CONTRACT.md) | Hard laws |
| [PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md) | Gates + decision model |
| [evidence/PRODUCTION_READINESS_MATRIX.md](../evidence/PRODUCTION_READINESS_MATRIX.md) | SHA-pinned scores |
| [MIGRATION_ENGINE.md](../MIGRATION_ENGINE.md) | Legacy engine / core notes |
| [ABRAXAS_LINEAGE.md](../ABRAXAS_LINEAGE.md) | Concept export only |
| [OPERATOR_RUNBOOK.md](../OPERATOR_RUNBOOK.md) | Operator day |
| [Design spec](../superpowers/specs/2026-08-04-hollersports-standalone-design.md) | Approved product design |
| [Implementation plan](../superpowers/plans/2026-08-04-hollersports-standalone-operator.md) | Task DAG |
