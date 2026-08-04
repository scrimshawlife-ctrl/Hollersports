<div align="center">

<img src="docs/images/hollersports-hero.jpg" alt="HollerSports — paper-only sports market intelligence operator hero" width="100%" />

# HollerSports

> **Betting advisory only** — no wallets, no book placement, **no real money**.\
> Free-first / fixture ingest → market-first candidates → paper simulation for ranking advice — fail-closed and deterministic.

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Package](https://img.shields.io/badge/hollersports-0.3.0-0B3D91)](packages/hollersports/pyproject.toml)
[![Purpose](https://img.shields.io/badge/purpose-advise%20only-0B3D91)](docs/SYSTEM_CONTRACT.md)
[![Money](https://img.shields.io/badge/real%20money-never-success)](docs/SYSTEM_CONTRACT.md)
[![Mode](https://img.shields.io/badge/mode-PAPER%20SIM-blue)](docs/SYSTEM_CONTRACT.md)
[![Books](https://img.shields.io/badge/live%20books-disabled-red)](docs/SYSTEM_CONTRACT.md)
[![Abraxas](https://img.shields.io/badge/Abraxas-concept%20lineage%20only-lightgrey)](docs/ABRAXAS_LINEAGE.md)
[![Advisory beta](https://img.shields.io/badge/advisory%20beta-local%20PASS-blue)](docs/PRODUCTION_READINESS.md)
[![License](https://img.shields.io/badge/license-Apache%202.0-informational)](LICENSE)

[Quick start](#quick-start) · [Atlas](docs/atlas/HOLLERSPORTS_ATLAS.md) · [Release notes](docs/RELEASE_NOTES.md) · [Production readiness](docs/PRODUCTION_READINESS.md) · [System contract](docs/SYSTEM_CONTRACT.md) · [Runbook](docs/OPERATOR_RUNBOOK.md) · [Design](docs/superpowers/specs/2026-08-04-hollersports-standalone-design.md)

</div>

---

## Why

Most “betting tools” either invent certainty or quietly become money rails. HollerSports does neither:

1. **Observe** markets with provenance and source health.  
2. **Advise** with scored candidates (`SHADOW_ONLY`) — what you *might* consider betting.  
3. **Simulate** advised tickets on paper to measure advice quality — **not** to move money.  
4. **Fail closed** when odds, lines, or provenance are missing.

> Strategies advise. Guards keep it paper. Ledgers score the advice. Humans decide — and bet elsewhere, if at all.

**No actual money is handled.** Bankroll / stake / ROI fields are simulation metrics for ranking and calibration.

## Status

**Readiness:** [local advisory beta **PASS**](docs/PRODUCTION_READINESS.md) on `main` @ merge PR #3 — see [post-merge assessment](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-08-04-post-merge.md).  
**Money / live books:** **never** — contract-forbidden.

| Track | State | Notes |
|-------|--------|--------|
| Governance + hashing | **shipped** | Authority locks, fail-closed helpers |
| Packet contracts v1 | **shipped** | Nine JSON Schemas + Pydantic |
| Fixture ingest + source health | **shipped** | `fixtures/day001` + `day002` (model fields) |
| Market-first strategies | **shipped** | Consensus · public fade · CLV; model edge gated (calibration) |
| Paper guard + ledger | **shipped** | `PAPER_ONLY`, hash-chained JSONL |
| Settlement / promotion / operator day | **shipped** | Fixture closed loop via `run_operator_day` |
| Golden 12-run + authority locks | **shipped** | `tests/golden/` |
| FastAPI `/v1` | **shipped** | `create_app` factory |
| Next.js Workbench (Cobalt) | **shipped** | Today · Book · Health |
| CI | **shipped** | `.github/workflows/ci.yml` |
| Real money / book placement | **never** | Advisory only |
| Local advisory beta | **PASS** | Merged main + CI + smoke |
| SaaS multi-tenant GA | **not claimed** | Local single-operator |

Full topology: **[docs/atlas/HOLLERSPORTS_ATLAS.md](docs/atlas/HOLLERSPORTS_ATLAS.md)**.

## Architecture (current)

```text
fixtures/day001 ──► source_health ──► MarketIngestionPacket
                                          │
                                          ▼
                              strategy competition
                              (SHADOW_ONLY candidates)
                                          │
                                          ▼
                              execution_guard (PAPER_ONLY)
                                          │
                                          ▼
                              paper ledger → settle → performance
                                          │
                                          ▼
                              promotion (review only) → dashboard projection
```

API + Next.js Workbench UI remain planned (Tasks 7–9).

## Quick start

```bash
git clone https://github.com/scrimshawlife-ctrl/Hollersports.git
cd Hollersports

python3 -m venv .venv && source .venv/bin/activate
make validate   # install + pytest + fixture smoke receipt
```

### Operator UI (local)

```bash
# terminal 1 — API
make api    # http://127.0.0.1:8000

# terminal 2 — Workbench
make web    # http://127.0.0.1:3000  (proxies /v1 → :8000)
```

### Ingest + compete on the fixture day

```python
from pathlib import Path
from hollersports.sources.fixture_adapter import load_fixture_day
from hollersports.pipelines.market_ingestion import run_market_ingestion
from hollersports.pipelines.strategy_competition import run_strategy_competition

day = load_fixture_day(Path("fixtures/day001"))
ingest = run_market_ingestion(day["ingest_payload"])
print(ingest["status"], ingest["authority"])  # INGESTED SHADOW_ONLY

comp = run_strategy_competition(ingest)
print(comp["status"], comp["candidate_count"])
```

### Paper a candidate

Use `hollersports.runes.execution_guard.run_execution_guard` with all gates `True` and `mode` always `PAPER_ONLY`. Append via `hollersports.paper.ledger.append_paper_entry`. See [OPERATOR_RUNBOOK.md](docs/OPERATOR_RUNBOOK.md).

## Package layout

| Path | Role |
|------|------|
| `packages/hollersports/` | Primary Python package (`hollersports` 0.3.0) |
| `schemas/json/` | Canonical `*.v1.schema.json` packet contracts |
| `fixtures/day001/` | Offline multi-league operator day |
| `fixtures/day002/` | Second day + `model_probability` for gated model edge |
| `tests/unit/` | TDD suite for the primary package |
| `docs/atlas/` | Repository atlas |
| `engine/` | Legacy slate isolation engine (migration reference) |
| `hollersports-core/` | Legacy feedback loop package |

## Day-one leagues

Architecture is multi-sport. Fixture pack and design day-one set:

**NBA · NFL · MLB · NHL · EPL · MLS** — markets v1: moneyline, spread, total.

## Documentation atlas

| Doc | Contents |
|-----|----------|
| **[docs/atlas/HOLLERSPORTS_ATLAS.md](docs/atlas/HOLLERSPORTS_ATLAS.md)** | Topology, surfaces, OBSERVED vs PLANNED |
| **[docs/SYSTEM_CONTRACT.md](docs/SYSTEM_CONTRACT.md)** | Ten non-negotiable laws |
| **[docs/ABRAXAS_LINEAGE.md](docs/ABRAXAS_LINEAGE.md)** | Concept-only lineage — no Abraxas install |
| **[docs/OPERATOR_RUNBOOK.md](docs/OPERATOR_RUNBOOK.md)** | Fixture operator day |
| **[docs/superpowers/specs/2026-08-04-hollersports-standalone-design.md](docs/superpowers/specs/2026-08-04-hollersports-standalone-design.md)** | Approved product design |
| **[docs/superpowers/plans/2026-08-04-hollersports-standalone-operator.md](docs/superpowers/plans/2026-08-04-hollersports-standalone-operator.md)** | Implementation plan (Tasks 1–10) |
| **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** | Legacy slate-engine integration notes |

## Governance seals

```text
CAPITAL_AUTHORITY=false
EXECUTION_AUTHORITY=false
LIVE_BOOKS=false
ABRAXAS_RUNTIME_REQUIRED=false
MODE=PAPER_ONLY
```

## Development

```bash
# focused tests
pytest tests/unit/test_governance.py -v
pytest tests/unit/ -q --ignore=hollersports-core

# editable install from packages/
pip install -e "packages/hollersports[dev]"
```

Implementation workstream: feature branch / plan Tasks 6–10 (settlement loop, API, Cobalt workbench UI, docs polish).

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Disclaimer

HollerSports is an **advisory and paper-simulation** tool. It does **not** handle real money, place wagers, custody funds, or connect to sportsbooks for execution. It does not guarantee predictive accuracy. Any real-world betting you do is outside this system and your responsibility; sports wagering may be restricted or illegal in your jurisdiction.
