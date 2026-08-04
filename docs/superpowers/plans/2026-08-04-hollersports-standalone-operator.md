# HollerSports Standalone Operator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a paper-only multi-sport market intelligence operator: free-first ingest → market-first strategies → paper portfolio → settle/performance/promotion → local Next.js Workbench (Cobalt) dashboard, with no live capital path and no Abraxas runtime dependency.

**Architecture:** Evolve `scrimshawlife-ctrl/Hollersports` into `packages/hollersports` (Python core + FastAPI) and `packages/operator-web` (Next.js). Canonical packet contracts live in `schemas/json/`. Pipelines are pure rune modules with fail-closed authority. Dashboard is PROJECTION_ONLY over HTTP JSON.

**Tech Stack:** Python ≥3.11, Pydantic v2, FastAPI, uvicorn, httpx, pytest; Next.js (App Router) + TypeScript; JSON Schema; fixture JSON packs.

**Spec:** `docs/superpowers/specs/2026-08-04-hollersports-standalone-design.md`

## Global Constraints

- **Python:** `>=3.11`
- **Authority:** `capital_authority` and `execution_authority` always `false` in v1
- **Mode:** all execution packets `mode: PAPER_ONLY`; no live book calls
- **Fail-closed:** missing odds/line/provenance → `NOT_COMPUTABLE` or `REJECTED`; never invent certainty
- **Day-one leagues:** NBA, NFL, MLB, NHL, EPL, MLS
- **Markets v1:** MONEYLINE, SPREAD, TOTAL only
- **Strategies v1:** MARKET_CONSENSUS_EDGE, PUBLIC_OVERREACTION_FADE, CLV_RETENTION_EDGE; model edge registered but gated off
- **Determinism:** same inputs → same packet hashes (12-run golden)
- **UI Hallmark lock:** Workbench · atmospheric · Cobalt · N3 · Ft4; Today · Book · Health IA
- **No Abraxas install** required to run tests or the operator
- **TDD:** write failing test → run fail → implement → run pass → commit each task
- **Preserve** existing `engine/` slate isolation and `hollersports-core` feedback ideas by relocating, not deleting behavior, until shims are green

---

## File map (create unless noted)

```text
packages/hollersports/
  pyproject.toml
  hollersports/
    __init__.py
    governance/
      authority.py          # Authority enum, always-false capital/execution
      fail_closed.py        # not_computable helpers
      gates.py              # calibration gate check (model edge)
    schemas/
      packets.py            # Pydantic models for all v1 packets
      hashing.py            # stable_json + packet_hash
    sources/
      registry.yaml
      registry.py
      fixture_adapter.py
      espn_scoreboard.py    # normalize + optional fetch
      odds_api.py           # normalize + optional fetch
    runes/
      source_health.py
      execution_guard.py
      bet_construct.py
      stake_sizer.py
      portfolio_simulator.py
      settlement_engine.py
      performance_tracker.py
      promotion_evaluator.py
      operator_project.py
    strategies/
      base.py
      registry.py
      market_consensus_edge.py
      public_overreaction_fade.py
      clv_retention_edge.py
      model_probability_edge.py  # gated off
    pipelines/
      market_ingestion.py
      strategy_competition.py
      paper_loop.py
      operator_day.py       # full day orchestration
    paper/
      ledger.py             # append-only JSONL + hash chain
      store.py              # paths under data/
    engine/                 # relocated from root engine/ (task 1)
    feedback/               # thin re-export / relocate from hollersports-core
    api/
      app.py
      routes.py
      deps.py

packages/operator-web/
  package.json
  tokens.css
  app/layout.tsx
  app/page.tsx              # Today
  app/book/page.tsx
  app/health/page.tsx
  components/...
  lib/api.ts

schemas/json/
  SourceHealthPacket.v1.schema.json
  MarketIngestionPacket.v1.schema.json
  StrategyCandidatePacket.v1.schema.json
  ExecutionPacket.v1.schema.json
  PaperPortfolioPacket.v1.schema.json
  SettlementPacket.v1.schema.json
  PerformancePacket.v1.schema.json
  PromotionPacket.v1.schema.json
  OperatorDashboardPacket.v1.schema.json

fixtures/
  day001/
    meta.json
    espn_events.json
    odds_records.json
    results.json

tests/
  unit/...
  integration/...
  golden/test_12_run_invariance.py
  golden/test_authority_locks.py

docs/
  SYSTEM_CONTRACT.md
  ABRAXAS_LINEAGE.md
  OPERATOR_RUNBOOK.md

data/                       # gitignored
.gitignore
pytest.ini
README.md                   # modify: honest PAPER_ONLY product
```

Legacy roots `engine/` and `hollersports-core/` remain until Task 1 relocates and leaves thin re-exports or deprecation notes so old imports do not silently break mid-migration.

---

### Task 1: Package scaffold + governance kernel

**Files:**
- Create: `packages/hollersports/pyproject.toml`
- Create: `packages/hollersports/hollersports/__init__.py`
- Create: `packages/hollersports/hollersports/governance/authority.py`
- Create: `packages/hollersports/hollersports/governance/fail_closed.py`
- Create: `packages/hollersports/hollersports/schemas/hashing.py`
- Create: `tests/unit/test_governance.py`
- Create: `pytest.ini`
- Create: `.gitignore` (include `data/`, `__pycache__/`, `.venv/`, `node_modules/`)
- Modify: root `requirements.txt` → point to package deps or replace with note to use package pyproject

**Interfaces:**
- Produces: `Authority` enum; `assert_no_live_capital(packet: dict) -> None`; `not_computable(schema_version: str, reason: str, **extra) -> dict`; `stable_json(obj) -> str`; `packet_hash(obj: dict) -> str`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_governance.py
from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.governance.fail_closed import not_computable
from hollersports.schemas.hashing import packet_hash, stable_json
import pytest

def test_authority_values():
    assert Authority.SHADOW_ONLY.value == "SHADOW_ONLY"
    assert Authority.PROJECTION_ONLY.value == "PROJECTION_ONLY"

def test_assert_no_live_capital_raises():
    with pytest.raises(ValueError, match="capital"):
        assert_no_live_capital({"capital_authority": True})

def test_not_computable_shape():
    p = not_computable("SourceHealthPacket.v1", "missing_provenance")
    assert p["status"] == "NOT_COMPUTABLE"
    assert p["authority"] == "SHADOW_ONLY"
    assert p["reason"] == "missing_provenance"
    assert p["capital_authority"] is False
    assert p["execution_authority"] is False

def test_packet_hash_deterministic():
    a = {"b": 1, "a": 2}
    assert packet_hash(a) == packet_hash({"a": 2, "b": 1})
    assert len(packet_hash(a)) == 64
```

- [ ] **Step 2: Run tests — expect fail**

```bash
cd /home/scrimshawlife/Hollersports
python -m venv .venv && . .venv/bin/activate
pip install -e packages/hollersports pytest pydantic
pytest tests/unit/test_governance.py -v
```

Expected: FAIL (module not found or import error)

- [ ] **Step 3: Implement**

`packages/hollersports/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hollersports"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.6",
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "httpx>=0.27",
  "jsonschema>=4.22",
  "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]

[tool.setuptools.packages.find]
where = ["."]
include = ["hollersports*"]

[tool.pytest.ini_options]
testpaths = ["../../tests"]
```

```python
# hollersports/governance/authority.py
from __future__ import annotations
from enum import Enum
from typing import Any, Mapping

class Authority(str, Enum):
    SHADOW_ONLY = "SHADOW_ONLY"
    FORECAST_SUPPORT = "FORECAST_SUPPORT"
    SHADOW_FIRST = "SHADOW_FIRST"
    PROJECTION_ONLY = "PROJECTION_ONLY"
    NOT_COMPUTABLE = "NOT_COMPUTABLE"

def assert_no_live_capital(packet: Mapping[str, Any]) -> None:
    if packet.get("capital_authority") is True:
        raise ValueError("capital_authority must be false in v1")
    if packet.get("execution_authority") is True:
        raise ValueError("execution_authority must be false in v1")
    if packet.get("mode") == "LIVE_APPROVED":
        raise ValueError("LIVE_APPROVED mode forbidden in v1")
```

```python
# hollersports/governance/fail_closed.py
from __future__ import annotations
from typing import Any

def not_computable(schema_version: str, reason: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": schema_version,
        "status": "NOT_COMPUTABLE",
        "authority": "SHADOW_ONLY",
        "reason": reason,
        "capital_authority": False,
        "execution_authority": False,
        "provenance": {},
    }
    out.update(extra)
    return out
```

```python
# hollersports/schemas/hashing.py
from __future__ import annotations
import hashlib
import json
from typing import Any

def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def packet_hash(obj: dict) -> str:
    return hashlib.sha256(stable_json(obj).encode("utf-8")).hexdigest()
```

Root `pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = packages/hollersports
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pip install -e "packages/hollersports[dev]"
pytest tests/unit/test_governance.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/hollersports pytest.ini .gitignore tests/unit/test_governance.py requirements.txt
git commit -m "feat: scaffold hollersports package and governance kernel"
```

---

### Task 2: Packet schemas + Pydantic models

**Files:**
- Create: `schemas/json/*.v1.schema.json` (all nine packets from file map)
- Create: `packages/hollersports/hollersports/schemas/packets.py`
- Create: `packages/hollersports/hollersports/schemas/validate.py`
- Create: `tests/unit/test_packets.py`

**Interfaces:**
- Produces: Pydantic models `SourceHealthPacket`, `MarketIngestionPacket`, `StrategyCandidatePacket`, `ExecutionPacket`, `PaperPortfolioPacket`, `SettlementPacket`, `PerformancePacket`, `PromotionPacket`, `OperatorDashboardPacket`
- Produces: `validate_packet(packet: dict, schema_name: str) -> dict` using jsonschema against `schemas/json/`
- Consumes: `Authority`, `packet_hash`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_packets.py
from hollersports.schemas.packets import SourceHealthPacket, StrategyCandidatePacket
from hollersports.schemas.validate import validate_packet

def test_source_health_roundtrip():
    p = SourceHealthPacket(
        status="PASS",
        source_id="FIXTURE",
        freshness_seconds=10,
        missing_required_fields=[],
        stale=False,
        provenance_present=True,
        health_score=1.0,
    )
    d = p.model_dump()
    assert d["authority"] == "SHADOW_ONLY"
    assert d["capital_authority"] is False
    validate_packet(d, "SourceHealthPacket.v1")

def test_candidate_always_shadow():
    c = StrategyCandidatePacket(
        status="CANDIDATE",
        run_id="R1",
        strategy_id="MARKET_CONSENSUS_EDGE",
        strategy_family="CONSENSUS",
        event_id="E1",
        market_id="M1",
        selection="HOME_ML",
        score=0.7,
        confidence=0.7,
        features={"consensus_score": 0.7},
        packet_refs={"market_ingestion": "R1"},
    )
    assert c.authority == "SHADOW_ONLY"
```

- [ ] **Step 2: Run — expect fail**

```bash
pytest tests/unit/test_packets.py -v
```

- [ ] **Step 3: Implement schemas + models**

Minimal JSON Schema pattern for each (example SourceHealth):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "SourceHealthPacket.v1",
  "type": "object",
  "required": ["schema_version", "status", "source_id", "authority", "capital_authority", "execution_authority"],
  "properties": {
    "schema_version": { "const": "SourceHealthPacket.v1" },
    "status": { "enum": ["PASS", "WARN", "FAIL", "NOT_COMPUTABLE"] },
    "source_id": { "type": "string" },
    "freshness_seconds": { "type": "number" },
    "missing_required_fields": { "type": "array", "items": { "type": "string" } },
    "stale": { "type": "boolean" },
    "provenance_present": { "type": "boolean" },
    "health_score": { "type": "number", "minimum": 0, "maximum": 1 },
    "authority": { "type": "string" },
    "capital_authority": { "const": false },
    "execution_authority": { "const": false },
    "provenance": { "type": "object" }
  },
  "additionalProperties": true
}
```

Repeat for other packets with fields from the design spec §5.4 and Notion Phase 7 shapes (status enums, `mode: PAPER_ONLY` on ExecutionPacket, promotion statuses, dashboard `panels` object).

```python
# hollersports/schemas/packets.py (excerpt — implement full set)
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field

class PacketBase(BaseModel):
    capital_authority: bool = False
    execution_authority: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)

class SourceHealthPacket(PacketBase):
    schema_version: Literal["SourceHealthPacket.v1"] = "SourceHealthPacket.v1"
    status: Literal["PASS", "WARN", "FAIL", "NOT_COMPUTABLE"]
    source_id: str
    freshness_seconds: float = 0
    missing_required_fields: list[str] = Field(default_factory=list)
    stale: bool = False
    provenance_present: bool = False
    health_score: float = 0.0
    authority: str = "SHADOW_ONLY"
```

```python
# hollersports/schemas/validate.py
from __future__ import annotations
import json
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parents[4]  # repo root from packages/hollersports/hollersports/schemas/
# If path depth wrong, resolve via env HOLLERSPORTS_ROOT or Path.cwd()

def schema_path(name: str) -> Path:
    root = Path.cwd()
    return root / "schemas" / "json" / f"{name}.schema.json"

def validate_packet(packet: dict, schema_name: str) -> dict:
    with open(schema_path(schema_name), encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(packet, schema)
    return packet
```

Fix `ROOT` resolution so tests from repo root work: prefer `Path.cwd() / "schemas/json"`.

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/unit/test_packets.py -v
```

- [ ] **Step 5: Commit**

```bash
git add schemas/json packages/hollersports/hollersports/schemas tests/unit/test_packets.py
git commit -m "feat: add v1 packet JSON schemas and Pydantic models"
```

---

### Task 3: Source health + fixture ingest

**Files:**
- Create: `packages/hollersports/hollersports/sources/registry.yaml`
- Create: `packages/hollersports/hollersports/sources/registry.py`
- Create: `packages/hollersports/hollersports/sources/fixture_adapter.py`
- Create: `packages/hollersports/hollersports/runes/source_health.py`
- Create: `packages/hollersports/hollersports/pipelines/market_ingestion.py`
- Create: `fixtures/day001/meta.json`, `espn_events.json`, `odds_records.json`
- Create: `tests/unit/test_source_health.py`
- Create: `tests/unit/test_market_ingestion.py`

**Interfaces:**
- Produces: `evaluate_source_health(payload, *, source_id, fetched_at, current_time, required_fields, source_refs, stale_after_seconds=900) -> dict`
- Produces: `run_market_ingestion(payload: dict) -> dict` → MarketIngestionPacket
- Produces: `load_fixture_day(path: Path) -> dict` with events + markets merged for strategies
- Consumes: fail_closed helpers

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_source_health.py
from hollersports.runes.source_health import evaluate_source_health

def test_missing_provenance_fails():
    h = evaluate_source_health(
        {"event_id": "E1"},
        source_id="X",
        fetched_at="2026-04-24T12:00:00+00:00",
        current_time="2026-04-24T12:01:00+00:00",
        required_fields=["event_id"],
        source_refs=None,
    )
    assert h["status"] == "FAIL"
    assert h["authority"] == "SHADOW_ONLY"
    assert h["capital_authority"] is False

def test_fresh_pass():
    h = evaluate_source_health(
        {"event_id": "E1", "markets": []},
        source_id="FIXTURE",
        fetched_at="2026-04-24T12:00:00+00:00",
        current_time="2026-04-24T12:01:00+00:00",
        required_fields=["event_id"],
        source_refs={"source": "FIXTURE"},
    )
    assert h["status"] == "PASS"
```

```python
# tests/unit/test_market_ingestion.py
from pathlib import Path
from hollersports.pipelines.market_ingestion import run_market_ingestion
from hollersports.sources.fixture_adapter import load_fixture_day

def test_fixture_ingest_ingested():
    day = load_fixture_day(Path("fixtures/day001"))
    packet = run_market_ingestion(day["ingest_payload"])
    assert packet["status"] == "INGESTED"
    assert packet["authority"] == "SHADOW_ONLY"
    assert "recommendation" not in packet
    assert len(packet["markets"]) >= 1
```

- [ ] **Step 2: Run — expect fail**

```bash
pytest tests/unit/test_source_health.py tests/unit/test_market_ingestion.py -v
```

- [ ] **Step 3: Implement source_health (design Phase 7 Step 1 logic), fixture adapter, pipeline**

Implement `evaluate_source_health` exactly as specified in design (missing fields / no provenance → FAIL; stale → WARN; else PASS; health_score 0–1).

`fixtures/day001/meta.json`:

```json
{
  "run_id": "FIX-DAY001",
  "fetched_at": "2026-04-24T18:00:00+00:00",
  "current_time": "2026-04-24T18:00:30+00:00",
  "leagues": ["NBA", "NFL", "MLB", "NHL", "EPL", "MLS"]
}
```

`odds_records.json` / `espn_events.json`: at least one event per day-one league family is ideal; minimum **one NBA event with moneyline markets** including fields strategies need: `consensus_score`, optional `public_bet_pct`/`handle_pct`, optional `clv_retention`.

`load_fixture_day` builds:

```python
{
  "ingest_payload": {
    "run_id": "...",
    "source_id": "FIXTURE",
    "source_type": "MANUAL",
    "fetched_at": "...",
    "current_time": "...",
    "required_fields": ["event_id", "markets"],
    "source_refs": {"source": "FIXTURE", "day": "day001"},
    "payload": {
      "event_id": "...",
      "sport": "BASKETBALL",
      "league": "NBA",
      "teams": ["BOS", "LAL"],
      "markets": [ ... ]
    }
  }
}
```

`run_market_ingestion`: health FAIL/NOT_COMPUTABLE → REJECTED/NOT_COMPUTABLE packet; else INGESTED with markets and `source_health` embedded.

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/unit/test_source_health.py tests/unit/test_market_ingestion.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/hollersports/hollersports/sources packages/hollersports/hollersports/runes/source_health.py packages/hollersports/hollersports/pipelines/market_ingestion.py fixtures tests/unit/test_source_health.py tests/unit/test_market_ingestion.py
git commit -m "feat: source health, fixture adapter, and market ingestion"
```

---

### Task 4: Strategy registry + competition loop

**Files:**
- Create: `packages/hollersports/hollersports/strategies/base.py`
- Create: `packages/hollersports/hollersports/strategies/market_consensus_edge.py`
- Create: `packages/hollersports/hollersports/strategies/public_overreaction_fade.py`
- Create: `packages/hollersports/hollersports/strategies/clv_retention_edge.py`
- Create: `packages/hollersports/hollersports/strategies/model_probability_edge.py`
- Create: `packages/hollersports/hollersports/strategies/registry.py`
- Create: `packages/hollersports/hollersports/pipelines/strategy_competition.py`
- Create: `packages/hollersports/hollersports/governance/gates.py`
- Create: `tests/unit/test_strategy_registry.py`
- Create: `tests/unit/test_strategy_competition.py`

**Interfaces:**
- Produces: `BaseStrategy.generate(packet) -> list[dict]`; `load_strategies(*, allow_model_edge: bool=False) -> list`; `run_strategy_competition(packet: dict, *, calibration: dict | None) -> dict`
- Produces: `calibration_allows_model_edge(gate: dict | None) -> bool` (default False)

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_strategy_registry.py
from hollersports.strategies.registry import load_strategies, registry_packet

def test_registry_three_market_strategies_by_default():
    ids = sorted(s.strategy_id for s in load_strategies())
    assert ids == [
        "CLV_RETENTION_EDGE",
        "MARKET_CONSENSUS_EDGE",
        "PUBLIC_OVERREACTION_FADE",
    ]
    assert registry_packet()["authority"] == "SHADOW_ONLY"

def test_model_edge_not_loaded_without_gate():
    ids = [s.strategy_id for s in load_strategies(allow_model_edge=False)]
    assert "MODEL_PROBABILITY_EDGE" not in ids
```

```python
# tests/unit/test_strategy_competition.py
from hollersports.pipelines.strategy_competition import run_strategy_competition

def _ingest():
    return {
        "schema_version": "MarketIngestionPacket.v1",
        "status": "INGESTED",
        "run_id": "R1",
        "event_id": "E1",
        "markets": [
            {
                "market_id": "M1",
                "selection": "HOME_ML",
                "consensus_score": 0.8,
                "public_bet_pct": 0.75,
                "handle_pct": 0.5,
                "fade_selection": "AWAY_ML",
                "clv_retention": 0.02,
            }
        ],
        "authority": "SHADOW_ONLY",
    }

def test_competition_emits_shadow_only_sorted():
    out = run_strategy_competition(_ingest())
    assert out["status"] == "COMPUTED"
    assert out["candidate_count"] >= 1
    for c in out["candidates"]:
        assert c["authority"] == "SHADOW_ONLY"
        assert c.get("capital_authority", False) is False

def test_invalid_ingest_not_computable():
    out = run_strategy_competition({"status": "REJECTED"})
    assert out["status"] == "NOT_COMPUTABLE"
```

- [ ] **Step 2: Run — expect fail**

```bash
pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_competition.py -v
```

- [ ] **Step 3: Implement strategies** using design Phase 7 Step 2 thresholds:

- consensus: `consensus_score >= 0.6`
- public fade: `public_bet_pct >= 0.7` and `gap >= 0.15`; if either field missing → emit nothing for that market (no invented splits)
- CLV: `clv_retention > 0`
- `build_candidate(...)` always sets `authority: SHADOW_ONLY`, `capital_authority: False`, `execution_authority: False`
- Deterministic sort: `(strategy_id, market_id, selection)`
- `MODEL_PROBABILITY_EDGE.generate` returns `[]` always in v1 (or only when `allow_model_edge` and gate true — still can return [] until model wired)

```python
# governance/gates.py
def calibration_allows_model_edge(gate: dict | None) -> bool:
    if not gate:
        return False
    return bool(gate.get("allow_forecast_weighting")) and gate.get("reliability_status") == "RELIABLE"
```

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_competition.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/hollersports/hollersports/strategies packages/hollersports/hollersports/pipelines/strategy_competition.py packages/hollersports/hollersports/governance/gates.py tests/unit/test_strategy_*.py
git commit -m "feat: market-first strategy registry and competition loop"
```

---

### Task 5: Execution guard + paper ledger

**Files:**
- Create: `packages/hollersports/hollersports/runes/execution_guard.py`
- Create: `packages/hollersports/hollersports/runes/bet_construct.py`
- Create: `packages/hollersports/hollersports/runes/stake_sizer.py`
- Create: `packages/hollersports/hollersports/runes/portfolio_simulator.py`
- Create: `packages/hollersports/hollersports/paper/ledger.py`
- Create: `packages/hollersports/hollersports/paper/store.py`
- Create: `packages/hollersports/hollersports/pipelines/paper_loop.py`
- Create: `tests/unit/test_execution_guard.py`
- Create: `tests/unit/test_paper_ledger.py`

**Interfaces:**
- Produces: `run_execution_guard(candidate: dict, context: dict) -> dict` (ExecutionPacket)
- Produces: `append_paper_entry(ledger_path, entry) -> dict` hash-chained
- Produces: `run_paper_loop(candidates: list[dict], context: dict) -> dict`

Gate keys in context (all must be True for APPROVED_FOR_PAPER):  
`source_health_gate`, `governance_gate`, `truth_gate` (can default True for fixture), `liquidity_gate`, `bankroll_gate`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_execution_guard.py
from hollersports.runes.execution_guard import run_execution_guard

def test_approves_paper_only():
    packet = run_execution_guard(
        {
            "strategy_id": "MARKET_CONSENSUS_EDGE",
            "event_id": "E1",
            "market_id": "M1",
            "selection": "HOME_ML",
            "score": 0.8,
            "packet_refs": {"x": "1"},
        },
        {
            "run_id": "R1",
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
        },
    )
    assert packet["status"] == "APPROVED_FOR_PAPER"
    assert packet["mode"] == "PAPER_ONLY"
    assert packet["authority"] == "SHADOW_FIRST"
    assert packet["capital_authority"] is False
    assert packet["execution_authority"] is False
    assert packet["stake"] > 0
    assert packet["stake"] <= 25.0

def test_failed_gate_rejects():
    packet = run_execution_guard(
        {"strategy_id": "X", "event_id": "E", "market_id": "M", "selection": "S", "score": 0.5, "packet_refs": {}},
        {"run_id": "R1", "price": 1.91, "bankroll": 1000, "human_max_stake": 25,
         "gates": {"source_health_gate": False, "governance_gate": True, "truth_gate": True, "liquidity_gate": True, "bankroll_gate": True}},
    )
    assert packet["status"] == "REJECTED"
```

```python
# tests/unit/test_paper_ledger.py
from pathlib import Path
from hollersports.paper.ledger import append_paper_entry, read_ledger

def test_append_only_hash_chain(tmp_path: Path):
    path = tmp_path / "paper.jsonl"
    e1 = append_paper_entry(path, {"entry_id": "1", "stake": 10.0})
    e2 = append_paper_entry(path, {"entry_id": "2", "stake": 5.0})
    rows = read_ledger(path)
    assert len(rows) == 2
    assert rows[1]["prev_hash"] == rows[0]["entry_hash"]
    assert e1["capital_authority"] is False
```

- [ ] **Step 2: Run — expect fail**

```bash
pytest tests/unit/test_execution_guard.py tests/unit/test_paper_ledger.py -v
```

- [ ] **Step 3: Implement**

- Stake: `min(human_max_stake, bankroll * 0.01 * score)` or similar deterministic formula; never zero when approved  
- Execution packet always `mode: PAPER_ONLY`  
- Ledger: JSONL lines with `entry_hash = sha256(stable_json({payload, prev_hash}))`  
- `store.py`: default root `Path("data/ledgers")` under cwd; create parents  

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/unit/test_execution_guard.py tests/unit/test_paper_ledger.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/hollersports/hollersports/runes/execution_guard.py packages/hollersports/hollersports/runes/bet_construct.py packages/hollersports/hollersports/runes/stake_sizer.py packages/hollersports/hollersports/runes/portfolio_simulator.py packages/hollersports/hollersports/paper packages/hollersports/hollersports/pipelines/paper_loop.py tests/unit/test_execution_guard.py tests/unit/test_paper_ledger.py
git commit -m "feat: paper execution guard and append-only paper ledger"
```

---

### Task 6: Settlement, performance, promotion, operator projection

**Files:**
- Create: `packages/hollersports/hollersports/runes/settlement_engine.py`
- Create: `packages/hollersports/hollersports/runes/performance_tracker.py`
- Create: `packages/hollersports/hollersports/runes/promotion_evaluator.py`
- Create: `packages/hollersports/hollersports/runes/operator_project.py`
- Create: `packages/hollersports/hollersports/pipelines/operator_day.py`
- Create: `fixtures/day001/results.json`
- Create: `tests/unit/test_settlement.py`
- Create: `tests/unit/test_performance_promotion.py`
- Create: `tests/integration/test_operator_day_fixture.py`

**Interfaces:**
- Produces: `settle_entry(entry, result) -> dict`
- Produces: `compute_performance(settled_entries: list[dict]) -> dict`
- Produces: `evaluate_promotion(performance: dict, evidence: dict) -> dict`
- Produces: `project_dashboard(state: dict) -> dict` authority PROJECTION_ONLY
- Produces: `run_operator_day(fixture_dir: Path | None, *, data_root: Path) -> dict` full closed loop

Promotion defaults from design §8.2. Fixture day may produce sample_size &lt; 100 → status `BLOCKED` (expected).

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_settlement.py
from hollersports.runes.settlement_engine import settle_entry

def test_settle_win():
    s = settle_entry(
        {"entry_id": "1", "selection": "HOME_ML", "stake": 10.0, "price": 1.91},
        {"result": "WIN", "source": "FIXTURE", "final_score": "110-100"},
    )
    assert s["status"] == "WIN"
    assert s["authority"] == "SHADOW_ONLY"
    assert "source" in s["provenance"]

def test_settle_pending_without_result():
    s = settle_entry(
        {"entry_id": "1", "selection": "HOME_ML", "stake": 10.0, "price": 1.91},
        None,
    )
    assert s["status"] == "PENDING"
```

```python
# tests/unit/test_performance_promotion.py
from hollersports.runes.performance_tracker import compute_performance
from hollersports.runes.promotion_evaluator import evaluate_promotion

def test_performance_excludes_pending():
    perf = compute_performance([
        {"status": "WIN", "stake": 10, "pnl": 9.1},
        {"status": "PENDING", "stake": 10, "pnl": 0},
        {"status": "LOSS", "stake": 10, "pnl": -10},
    ])
    assert perf["sample_size"] == 2
    assert perf["authority"] == "SHADOW_ONLY"

def test_promotion_blocked_small_sample():
    prom = evaluate_promotion(
        {"sample_size": 2, "roi": 0.1, "max_drawdown": 0.05, "clv_retention": 0.0},
        {"source_health_pass_rate": 1.0, "invariance_pass": True, "regimes": 1, "market_types": 1, "unresolved_blockers": 0},
    )
    assert prom["status"] == "BLOCKED"
    assert "sample_size" in str(prom["failed_gates"]).lower() or any("sample" in g.lower() for g in prom["failed_gates"])
```

```python
# tests/integration/test_operator_day_fixture.py
from pathlib import Path
from hollersports.pipelines.operator_day import run_operator_day

def test_closed_loop_fixture(tmp_path: Path):
    out = run_operator_day(Path("fixtures/day001"), data_root=tmp_path)
    assert out["ingest"]["status"] == "INGESTED"
    assert out["competition"]["status"] == "COMPUTED"
    assert out["dashboard"]["authority"] == "PROJECTION_ONLY"
    assert out["dashboard"].get("capital_authority") is False
    assert "Place bet" not in str(out)
```

- [ ] **Step 2: Run — expect fail**

```bash
pytest tests/unit/test_settlement.py tests/unit/test_performance_promotion.py tests/integration/test_operator_day_fixture.py -v
```

- [ ] **Step 3: Implement engines + `run_operator_day`**

Sequence in `run_operator_day`:

1. load fixture → ingest  
2. compete  
3. for each candidate (or top-N by score, N=min(5, len)): paper approve with all gates True for fixture  
4. settle using `results.json` keyed by `event_id`/`market_id` when present  
5. performance + promotion  
6. dashboard projection with panels: paper summary, settlement queue, performance, promotion, sources  

`project_dashboard` must set `authority: PROJECTION_ONLY` and never include live mode.

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/unit/test_settlement.py tests/unit/test_performance_promotion.py tests/integration/test_operator_day_fixture.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/hollersports/hollersports/runes packages/hollersports/hollersports/pipelines/operator_day.py fixtures/day001/results.json tests/unit/test_settlement.py tests/unit/test_performance_promotion.py tests/integration
git commit -m "feat: settlement, performance, promotion, and fixture operator day"
```

---

### Task 7: FastAPI surface

**Files:**
- Create: `packages/hollersports/hollersports/api/app.py`
- Create: `packages/hollersports/hollersports/api/routes.py`
- Create: `packages/hollersports/hollersports/api/deps.py`
- Create: `tests/integration/test_api.py`

**Interfaces:**
- Produces: FastAPI app with routes from design §5.6
- `GET /v1/health`, `POST /v1/runs/ingest`, `POST /v1/runs/compete`, `POST /v1/runs/paper`, `POST /v1/runs/settle`, `GET /v1/dashboard`, `GET /v1/portfolio`, `GET /v1/promotion`
- In-memory + disk store under `data/` (or `HOLLER_DATA_ROOT`)

- [ ] **Step 1: Write failing API tests**

```python
# tests/integration/test_api.py
from fastapi.testclient import TestClient
from hollersports.api.app import create_app

def test_health():
    client = TestClient(create_app(data_root="/tmp/holler-test-api"))
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["capital_authority"] is False

def test_fixture_ingest_and_dashboard(tmp_path):
    client = TestClient(create_app(data_root=str(tmp_path)))
    r = client.post("/v1/runs/ingest", json={"fixture": "day001"})
    assert r.status_code == 200
    assert r.json()["status"] in ("INGESTED", "REJECTED")
    r2 = client.post("/v1/runs/compete", json={})
    assert r2.status_code == 200
    d = client.get("/v1/dashboard")
    assert d.status_code == 200
    assert d.json()["authority"] == "PROJECTION_ONLY"
```

- [ ] **Step 2: Run — expect fail**

```bash
pip install -e "packages/hollersports[dev]"
pytest tests/integration/test_api.py -v
```

- [ ] **Step 3: Implement `create_app(data_root: str | None = None)`** with CORS for `http://localhost:3000`, routes calling pipelines, last-run state in a simple `RunStore` class writing under `data_root/runs`.

- [ ] **Step 4: Run — expect pass**

```bash
pytest tests/integration/test_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/hollersports/hollersports/api tests/integration/test_api.py
git commit -m "feat: FastAPI packet API for operator day"
```

---

### Task 8: Golden invariance + authority locks

**Files:**
- Create: `tests/golden/test_12_run_invariance.py`
- Create: `tests/golden/test_authority_locks.py`

**Interfaces:**
- Consumes: `run_operator_day`, all packet builders

- [ ] **Step 1: Write failing tests**

```python
# tests/golden/test_12_run_invariance.py
from pathlib import Path
from hollersports.pipelines.operator_day import run_operator_day
from hollersports.schemas.hashing import packet_hash

def test_twelve_run_same_hashes(tmp_path: Path):
    hashes = []
    for i in range(12):
        out = run_operator_day(Path("fixtures/day001"), data_root=tmp_path / f"r{i}")
        # hash core deterministic packets (exclude wall-clock if any — strip timestamps if present)
        core = {
            "ingest_status": out["ingest"]["status"],
            "candidates": out["competition"].get("candidates", []),
            "promotion_status": out["promotion"]["status"],
        }
        hashes.append(packet_hash(core))
    assert len(set(hashes)) == 1
```

```python
# tests/golden/test_authority_locks.py
from pathlib import Path
from hollersports.pipelines.operator_day import run_operator_day
from hollersports.governance.authority import assert_no_live_capital

def test_no_live_flags_in_operator_day(tmp_path: Path):
    out = run_operator_day(Path("fixtures/day001"), data_root=tmp_path)
    for key in ("ingest", "competition", "dashboard", "performance", "promotion"):
        assert_no_live_capital(out[key] if isinstance(out[key], dict) else {})
    for c in out["competition"].get("candidates", []):
        assert_no_live_capital(c)
        assert c.get("mode") != "LIVE_APPROVED"
```

- [ ] **Step 2: Run — may fail if timestamps leak into candidates**

```bash
pytest tests/golden/ -v
```

- [ ] **Step 3: Fix determinism** — strategies/pipelines must not put `datetime.now()` into scored candidate features; use only ingest `fetched_at` when needed. Re-run until 12 hashes match.

- [ ] **Step 4: Full unit+integration+golden green**

```bash
pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/golden packages/hollersports
git commit -m "test: golden 12-run invariance and authority locks"
```

---

### Task 9: Operator web shell (Hallmark Workbench / Cobalt)

**Files:**
- Create: `packages/operator-web/package.json`
- Create: `packages/operator-web/tsconfig.json`
- Create: `packages/operator-web/next.config.ts` (or `.mjs`) with rewrites `/v1/*` → `http://127.0.0.1:8000/v1/*`
- Create: `packages/operator-web/tokens.css` (Cobalt OKLCH tokens + Hallmark stamp comment)
- Create: `packages/operator-web/app/globals.css`
- Create: `packages/operator-web/app/layout.tsx`
- Create: `packages/operator-web/app/page.tsx` (Today)
- Create: `packages/operator-web/app/book/page.tsx`
- Create: `packages/operator-web/app/health/page.tsx`
- Create: `packages/operator-web/components/Shell.tsx`
- Create: `packages/operator-web/components/AuthorityChip.tsx`
- Create: `packages/operator-web/components/DataTable.tsx`
- Create: `packages/operator-web/lib/api.ts`
- Create: `packages/operator-web/README.md`

**Interfaces:**
- Produces: UI calling `lib/api.ts` → `/v1/*`
- No “Place bet” string anywhere in source

- [ ] **Step 1: Scaffold Next.js app**

```bash
cd packages
npx create-next-app@15 operator-web --typescript --eslint --app --src-dir=false --import-alias "@/*" --tailwind false --use-npm
# or manual package.json with next@15 react@19
```

If create-next-app conflicts with plan layout, hand-roll minimal App Router package.

- [ ] **Step 2: Add tokens.css with stamp**

First line of `tokens.css`:

```css
/* Hallmark · macrostructure: Workbench · genre: atmospheric · theme: Cobalt · nav: N3 · footer: Ft4
 * tone: technical-austere · pre-emit critique: P5 H4 E4 S5 R5 V4
 */
:root {
  --color-paper: oklch(18% 0.02 250);
  --color-paper-2: oklch(22% 0.02 250);
  --color-ink: oklch(92% 0.02 250);
  --color-muted: oklch(70% 0.02 250);
  --color-accent: oklch(62% 0.14 250);
  --color-accent-ink: oklch(18% 0.02 250);
  --color-warn: oklch(75% 0.12 85);
  --color-fail: oklch(65% 0.16 25);
  --font-display: "Space Grotesk", system-ui, sans-serif;
  --font-body: "IBM Plex Sans", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
}
```

- [ ] **Step 3: Shell with N3 rail (Today / Book / Health) + Ft4 colophon**

Colophon text: `PAPER_ONLY · capital_authority=false · schema v1`

- [ ] **Step 4: Today page**

- Overview fields from `GET /v1/dashboard` only; missing → `—` + reason  
- Actions: buttons calling POST ingest (`fixture: day001` default), compete, paper, settle  
- Button states: disabled when loading; no celebratory toast  

- [ ] **Step 5: Book page**

- Table of candidates (tabular-nums on score)  
- Select rows → paper  
- Portfolio table from `GET /v1/portfolio`  

- [ ] **Step 6: Health page**

- Sources / performance / promotion / run log sections  
- AuthorityChip three tones only  

- [ ] **Step 7: Guardrail grep**

```bash
cd packages/operator-web && ! rg -n "Place bet|LIVE_APPROVED|placeBet" --glob '!node_modules/**' .
```

Expected: no matches (exit 0 with `!`)

- [ ] **Step 8: Build**

```bash
cd packages/operator-web && npm run build
```

Expected: success

- [ ] **Step 9: Commit**

```bash
git add packages/operator-web
git commit -m "feat: Cobalt workbench operator UI (Today, Book, Health)"
```

---

### Task 10: Docs + README + engine relocation notes

**Files:**
- Create: `docs/SYSTEM_CONTRACT.md`
- Create: `docs/ABRAXAS_LINEAGE.md`
- Create: `docs/OPERATOR_RUNBOOK.md`
- Modify: `README.md` — product identity PAPER_ONLY, how to run API + UI + fixtures
- Create: `docs/MIGRATION_ENGINE.md` short note: root `engine/` and `hollersports-core/` kept for reference; new path is `packages/hollersports`; model-edge wiring is post-v1 optional task

Optional if time in this task: move `engine/` modules into `packages/hollersports/hollersports/engine/` and leave root shims importing from new path; keep existing `tests/test_state_isolation.py` green via path update.

- [ ] **Step 1: Write SYSTEM_CONTRACT.md** — copy the ten laws from design §1.3 + promotion never live

- [ ] **Step 2: Write ABRAXAS_LINEAGE.md** — concept table from design §4

- [ ] **Step 3: Write OPERATOR_RUNBOOK.md**

```markdown
# Operator runbook

## Fixture day
1. `uvicorn hollersports.api.app:create_app --factory --port 8000` from packages/hollersports with PYTHONPATH/install
2. `cd packages/operator-web && npm run dev`
3. Today → Ingest fixture day001 → Compete → Paper → (optional) Settle
4. Health → verify promotion BLOCKED until sample gates pass

## Live free sources
Requires API keys in env (document `THE_ODDS_API_KEY` etc.). Without keys, fixture mode only.
```

- [ ] **Step 4: Rewrite README** — remove any implication of live wagering or Abraxas-required runtime

- [ ] **Step 5: Final test sweep**

```bash
cd /home/scrimshawlife/Hollersports
. .venv/bin/activate
pytest tests/ -v
cd packages/operator-web && npm run build
```

Expected: all green

- [ ] **Step 6: Commit**

```bash
git add docs README.md packages/hollersports engine tests
git commit -m "docs: system contract, Abraxas lineage, operator runbook, README"
```

---

## Self-review (plan vs spec)

| Spec section | Task coverage |
|--------------|---------------|
| Hard laws / authority | T1, T5, T8 |
| Packet schemas | T2 |
| Free-first / fixture ingest + source health | T3 (live ESPN/Odds adapters can be thin stubs behind fixture-first; full live fetch optional enhancement inside T3 if keys present) |
| Market-first strategies + gated model edge | T4 |
| Paper loop | T5–T6 |
| Dashboard projection API | T6–T7 |
| Hallmark UI Today/Book/Health | T9 |
| Golden 12-run + locks | T8 |
| Docs / lineage | T10 |
| Day-one multi-league | Fixture meta + markets in T3; adapters normalize league field |
| Evolve existing engine | T10 relocation note; model edge stub T4 |

**Placeholder scan:** none intentional. Live HTTP adapters beyond fixture may ship as normalize-only + optional fetch in T3 without blocking the closed loop.

**Type consistency:** packets use shared `schema_version` strings; `run_operator_day` returns keys `ingest`, `competition`, `paper`, `settlements`, `performance`, `promotion`, `dashboard` — API and UI must use the same names.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-04-hollersports-standalone-operator.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
