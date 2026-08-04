# HollerSports Atlas

Topology card for the standalone operator repository.  
Vocabulary: **OBSERVED** (in tree now) · **PLANNED** (design + plan) · **NOT_COMPUTABLE** (missing evidence).

## Identity

| | |
|--|--|
| **What it is** | Paper-only sports market intelligence operator: free-first / fixture ingest → market-first strategies → paper ledger, with fail-closed authority. |
| **What it is not** | Live book executor, Abraxas runtime dependency, or autonomous capital system. |
| **Package** | `hollersports` **0.2.0** (`packages/hollersports`) |
| **Mode** | `PAPER_ONLY` · `capital_authority=false` · `execution_authority=false` |
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

### Source health + fixture ingest — OBSERVED

| | |
|--|--|
| **What it is** | Registry, fixture day pack, source health rune, market ingestion pipeline. |
| **What it is not** | Recommendation engine; live network is optional future. |
| **Paths** | `hollersports/sources/`, `hollersports/runes/source_health.py`, `hollersports/pipelines/market_ingestion.py`, `fixtures/day001/` |
| **Tests** | `tests/unit/test_source_health.py`, `test_market_ingestion.py` |

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

### Settlement / performance / promotion / operator day — PLANNED

| | |
|--|--|
| **What it is** | Design + plan Tasks 6–8: settle, metrics, promotion gates, full fixture day, golden 12-run. |
| **What it is not** | Present as shipped until modules + tests land. |
| **Paths** | [plan Task 6–8](../superpowers/plans/2026-08-04-hollersports-standalone-operator.md) |

### FastAPI packet API — PLANNED

| | |
|--|--|
| **What it is** | `/v1/runs/*`, `/v1/dashboard`, `/v1/portfolio`, `/v1/promotion` |
| **Paths** | plan Task 7 |

### Operator web (Workbench / Cobalt) — PLANNED

| | |
|--|--|
| **What it is** | Next.js local dashboard: Today · Book · Health; Hallmark Workbench + Cobalt + N3 + Ft4. |
| **What it is not** | Place-bet UI. |
| **Paths** | plan Task 9 · design §6 |

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

## Pipeline (target)

```text
fixtures | free sources
    → source_health
    → MarketIngestionPacket
    → strategy competition (SHADOW_ONLY candidates)
    → execution_guard (PAPER_ONLY)
    → paper ledger
    → settle → performance → promotion   [PLANNED]
    → operator projection / dashboard    [PLANNED]
```

## Governance seals

```text
CAPITAL_AUTHORITY=false
EXECUTION_AUTHORITY=false
LIVE_BOOKS=false
ABRAXAS_RUNTIME_REQUIRED=false
MODE=PAPER_ONLY
```

## Related docs

| Doc | Role |
|-----|------|
| [SYSTEM_CONTRACT.md](../SYSTEM_CONTRACT.md) | Hard laws |
| [ABRAXAS_LINEAGE.md](../ABRAXAS_LINEAGE.md) | Concept export only |
| [OPERATOR_RUNBOOK.md](../OPERATOR_RUNBOOK.md) | Operator day |
| [Design spec](../superpowers/specs/2026-08-04-hollersports-standalone-design.md) | Approved product design |
| [Implementation plan](../superpowers/plans/2026-08-04-hollersports-standalone-operator.md) | Task DAG |
