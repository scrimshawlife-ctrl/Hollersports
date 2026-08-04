# HollerSports Standalone Operator — Design Spec

**Date:** 2026-08-04  
**Status:** Approved (brainstorm)  
**Repo:** `scrimshawlife-ctrl/Hollersports`  
**Approach:** Evolve existing repo (Approach 1)

---

## 1. Product identity

HollerSports is a **standalone sports market intelligence operator**: free-first data → market-structure candidates → paper-only portfolio → settlement/calibration → local Next.js dashboard.

It **reimplements useful Abraxas governance concepts** (authority lanes, fail-closed packets, rune-as-pure-function modules, dual-lane doctrine, promotion gates) **inside this repository**. There is **no Abraxas runtime dependency**. Optional future export of Abraxas-shaped shadow packets is allowed; import of Abraxas to boot is not.

### 1.1 Primary job (v1)

**Operator product (local dashboard):** paper-trading lab plus a local web dashboard as the daily surface.

### 1.2 V1 done bar

Closed paper loop on day-one leagues:

`ingest → source health → strategy candidates → paper portfolio → settlement → performance / promotion panels → dashboard`

One sport-day can run end-to-end with **fixtures** if live feeds are down. **No live betting.**

### 1.3 Hard laws (non-negotiable)

1. **No live capital execution** — paper only; dashboard cannot place bets.  
2. **Fail closed** — missing provenance, odds, or line → `NOT_COMPUTABLE` or reject; never invent certainty.  
3. **Strategies propose, never execute.**  
4. **Projection is read-only** — UI only displays packets; mutations go through API commands with explicit authority.  
5. **Determinism** — same inputs → same packet hashes (golden 12-run invariance).  
6. **Calibration gate** — model edge cannot weight tickets until calibration gates pass.  
7. **Multi-sport core** — sport-agnostic event/market model; day-one leagues listed below.  
8. **`capital_authority` and `execution_authority` are always false in v1.**

---

## 2. Scope decisions (locked)

| Decision | Choice |
|----------|--------|
| Product form | Operator product: Python core + local Next.js dashboard |
| Architecture breadth | Multi-sport from day one |
| Day-one leagues | NBA, NFL, MLB, NHL, soccer (EPL, MLS) |
| Market types v1 | MONEYLINE, SPREAD, TOTAL |
| Edge posture | Hybrid, **market-first**; model probability edge pluggable and calibration-gated |
| Stack | Next.js UI + Python (FastAPI) intelligence API |
| Abraxas coupling | Concept-only extract (no Abraxas install) |
| Repo strategy | Evolve existing Hollersports repo |

### 2.1 Explicitly out of v1

- Live sportsbook execution or “Place bet” UI  
- Player props / DFS (PrizePicks-style) as primary surface  
- Multi-user auth / teams  
- Abraxas runtime, YGGDRASIL engine, AAL-Viz dependency  
- Symbolic / ritual / slang overlays as ticket weights  
- Paid data vendors as required path  
- Invented marketing metrics or fake KPI dashboards  

---

## 3. Architecture

### 3.1 Runtime topology

```text
┌─────────────────────┐     HTTP/JSON packets      ┌──────────────────────┐
│  operator-web       │ ◄────────────────────────► │  hollersports API     │
│  (Next.js :3000)    │     projection-only UI     │  (FastAPI :8000)      │
└─────────────────────┘                            └──────────┬───────────┘
                                                              │
                         pipelines + runes                    │
                         sources → health → strategies →      │
                         guard → paper → settle →             │
                         performance → promotion → project    │
                                                              │
                                              fixtures | free APIs | local ledger
```

### 3.2 Repo shape

```text
Hollersports/
├── packages/
│   ├── hollersports/              # Python package (intelligence core)
│   │   ├── governance/            # authority, gates, fail-closed helpers
│   │   ├── schemas/               # Pydantic models (mirror JSON schemas)
│   │   ├── sources/               # free-first adapters + registry
│   │   ├── runes/                 # pure modules (source_health, settle, …)
│   │   ├── strategies/            # market-first families + pluggable model edge
│   │   ├── pipelines/             # orchestration
│   │   ├── paper/                 # portfolio ledger, settlement, performance
│   │   ├── engine/                # evolved slate isolation + optional MC model edge
│   │   ├── feedback/              # append-only ledgers, prior updates (opt-in)
│   │   └── api/                   # FastAPI app
│   └── operator-web/              # Next.js local dashboard
├── schemas/json/                  # versioned *.v1.schema.json (canonical)
├── fixtures/                      # offline slate packs for tests + demo day
├── data/                          # local runtime (gitignored): ledgers, runs, cache
├── docs/
│   ├── SYSTEM_CONTRACT.md
│   ├── ABRAXAS_LINEAGE.md
│   ├── OPERATOR_RUNBOOK.md
│   └── superpowers/specs/         # this document
└── tests/
    ├── unit/
    ├── integration/
    └── golden/                    # 12-run invariance
```

### 3.3 Authority model

Every packet carries an authority field. Values used in v1:

| Authority | Meaning |
|-----------|---------|
| `SHADOW_ONLY` | Observation / candidate only |
| `FORECAST_SUPPORT` | May inform ranking after calibration |
| `SHADOW_FIRST` / paper path | Paper portfolio path (`mode: PAPER_ONLY`) |
| `PROJECTION_ONLY` | Dashboard read models |
| `NOT_COMPUTABLE` | Fail-closed incomplete |

### 3.4 Domain model (sport-agnostic)

```text
Sport → League → Event → Market → Selection
                      ↘ Outcome (final)
```

Adapters map vendor IDs → stable internal `event_id` / `market_id`.

### 3.5 What evolves from current code

| Today | Becomes |
|-------|---------|
| `engine/reset_state.py`, `slate_runner.py` | `packages/hollersports/engine/` — multi-sport slate isolation + fingerprints |
| `engine/simulation.py`, `picks_generator.py` | model-edge plugin (calibration-gated) |
| `hollersports-core/` | `feedback/` + ledger primitives under `paper/` |
| Root tests / README | Expanded tests; honest PAPER_ONLY product docs |

**Preserve:** state isolation, source fingerprints, no slate bleed, append-only feedback idea, controlled calibration memory opt-in.

---

## 4. Abraxas concept export (concept-only)

Reimplemented inside HollerSports; documented in `docs/ABRAXAS_LINEAGE.md`:

| Abraxas idea | Standalone form |
|--------------|-----------------|
| Authority lanes | Packet `authority` + hard locks |
| Fail-closed | `NOT_COMPUTABLE` / REJECTED; no invented odds |
| Calibration gate | Model edge offline until gate packet allows `FORECAST_SUPPORT` |
| Promotion gate | Paper metrics → review statuses only |
| Dual-lane | Market microstructure free to score; model/symbolic influence gated |
| Runes | Named pure modules under `runes/` (not ABX runtime) |
| Packet spine | Versioned JSON schemas as API contract |
| YGGDRASIL branches | Internal pipeline stages: MARKET_INTELLIGENCE, CAPITAL_POLICY (paper), VALIDATION, PROJECTION |
| Source registry + health | `sources/registry.yaml` + `source_health` before strategies |
| Append-only ledgers | Paper + outcome ledgers with hash chain |

**Not imported for v1:** full ABX-Runes engine, YGGDRASIL runtime, AAL-Viz, Canon Spine service, ritual/slang weighting.

**Dependency direction:** HollerSports may *export* Abraxas-shaped shadow packets later; it never *requires* Abraxas to start.

---

## 5. Components and data flow

### 5.1 Pipeline (one operator day)

```text
External / fixtures
        │
        ▼
Source adapters + registry.yaml
        │
        ▼
source_health  →  FAIL: reject  |  WARN: ingest+flag  |  PASS: ingest
        │
        ▼
MarketIngestionPacket.v1  (SHADOW_ONLY)
        │
        ▼
Strategy registry + competition loop
  (market-first always; model-edge only if calibration allows)
        │
        ▼
StrategyCandidatePacket.v1[]  (SHADOW_ONLY)
        │
        ▼
execution_guard + bet_construct + stake_sizer  (paper only)
        │
        ▼
ExecutionPacket.v1  (mode: PAPER_ONLY)
        │
        ▼
portfolio_simulate → paper ledger
        │
        ▼  (await final result)
settlement → performance → promotion_evaluate
        │
        ▼
operator_project → OperatorDashboardPacket / HollerDashboardState
        │
        ▼
Next.js panels (PROJECTION_ONLY)
```

### 5.2 Component responsibilities

| Component | Does | Does not |
|-----------|------|----------|
| `governance/` | authority enums, gate helpers, fail-closed builders | business scoring |
| `sources/` | fetch, normalize, registry | recommendations |
| `runes/source_health` | freshness, required fields, provenance | create candidates |
| `strategies/` | emit scored candidates | execute, promote, size stakes |
| `runes/execution_guard` | paper approve/reject with reason codes | live book calls |
| `paper/` | ledger, settle, performance, promotion | mutate market data |
| `engine/` | slate isolation, fingerprints, optional MC model edge | bypass gates |
| `feedback/` | residual → prior updates (opt-in) | auto-enable forecast weighting |
| `api/` | run pipeline steps, serve packets | UI authority |
| `operator-web` | panels, filters, refresh | write promotion/capital truth |

### 5.3 Day-one strategy families (market-first)

1. **MARKET_CONSENSUS_EDGE** — multi-book consensus / price agreement  
2. **PUBLIC_OVERREACTION_FADE** — public vs handle gap when splits available; otherwise skip or `NOT_COMPUTABLE` (never invent split %)  
3. **CLV_RETENTION_EDGE** — open→close retention when closing lines attach  

**Model edge:** wraps evolved `SlateRunner` / Monte Carlo as `MODEL_PROBABILITY_EDGE`. Registered in the strategy registry but **disabled for ticket weighting** until `CalibrationGate` allows `FORECAST_SUPPORT`.

### 5.4 Packet contracts (v1 minimum)

All packets share: `schema_version`, `status`, `authority`, `provenance` (hashes, timestamps, source refs). Canonical definitions live under `schemas/json/`; Pydantic mirrors them.

| Packet | Role |
|--------|------|
| `SourceHealthPacket.v1` | PASS / WARN / FAIL |
| `MarketIngestionPacket.v1` | Normalized event + markets |
| `StrategyCandidatePacket.v1` | Proposed edge |
| `ExecutionPacket.v1` | Paper-approved construct or reject |
| `PaperPortfolioPacket.v1` | Ledger entry |
| `SettlementPacket.v1` | Outcome-linked settle |
| `PerformancePacket.v1` | Portfolio metrics |
| `PromotionPacket.v1` | Gate report only |
| `OperatorDashboardPacket.v1` | UI projection |
| `HollerDashboardState.v1` | Aggregated dashboard state (if needed for multi-panel projection) |

### 5.5 Storage (local v1)

| Store | Content |
|-------|---------|
| `data/ledgers/` | append-only paper + outcome ledgers (hash-chained) |
| `data/runs/` | per-run packet dumps (reproducibility) |
| `data/cache/` | source HTTP cache (TTL + rate limits) |
| `fixtures/` | offline packs for demo + CI |

No cloud database required. Prefer JSONL + hash chain initially (matches existing core). SQLite is a later option if JSONL becomes painful.

### 5.6 API surface (FastAPI)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/runs/ingest` | Source fetch + health + ingest |
| `POST` | `/v1/runs/compete` | Strategy competition on named/last ingest |
| `POST` | `/v1/runs/paper` | Guard → construct → paper ledger |
| `POST` | `/v1/runs/settle` | Attach results + settle |
| `GET` | `/v1/dashboard` | Latest operator dashboard packet |
| `GET` | `/v1/portfolio` | Paper book + performance |
| `GET` | `/v1/promotion` | Promotion gate status |
| `GET` | `/v1/health` | API + source registry summary |

Mutating routes return full packets with authority fields. UI only calls these routes.

### 5.7 Error and missing-data policy

| Condition | Behavior |
|-----------|----------|
| Source FAIL | Ingest `REJECTED`; strategies not run |
| No odds | Market `NOT_COMPUTABLE`; no candidate |
| No public splits | Public-fade skips or NOT_COMPUTABLE; no fake percentages |
| No final score | Settlement stays `PENDING`; promotion sample excludes it |
| Calibration incomplete | Model edge offline; market strategies still run |
| Any live-execution flag | Hard fail tests + API refuse |

---

## 6. Operator dashboard (Next.js)

### 6.1 Hallmark lock (required before UI implementation)

| Axis | Value |
|------|--------|
| Genre | atmospheric (ops / late-night tool) |
| Macrostructure | Workbench |
| Theme | Cobalt (cool paper · grotesk + mono; not Continuity-Forge Terminal/phosphor) |
| Nav | N3 side-rail (dense labels; active = left hairline + surface lift) |
| Footer | Ft4 dense colophon |
| Enrichment | none — typography + tables only |
| Tokens | `packages/operator-web/tokens.css` first; OKLCH only; no inline colors/fonts |
| Stamp | `/* Hallmark · macrostructure: Workbench · genre: atmospheric · theme: Cobalt · nav: N3 · footer: Ft4 */` |

**Visual one-liner:** scoreboard workbench — dense tables, mono IDs/hashes, cool tinted paper, single accent for WARN/FAIL only.

Hallmark audit of the draft shell (2026-08-04) required: declare structural fingerprint, collapse flat 9-item IA, ban invented overview metrics, token discipline, tabular-nums, three-tone chips, silent success, contrast contract, Ft4 colophon, avoid card-in-card and Continuity Terminal clone-by-default.

### 6.2 Information architecture

Three primary destinations (not nine equal peers):

| Primary | Contains | Operator job |
|---------|----------|--------------|
| **Today** | Overview strip + run actions (ingest / compete / paper / settle) + last `run_id` | Run the day |
| **Book** | Candidates → Paper book → Settlement (one continuous book flow) | Select, paper, settle |
| **Health** | Sources · Performance · Promotion · Run log | Trust the system |

### 6.3 Shell rules

- **Mode** is a **locked status** (`PAPER_ONLY`), not a live/paper toggle.  
- **One containment layer:** shell + hairline rules / gap — no card-in-card, no vanity KPI tiles.  
- **Tables:** `font-variant-numeric: tabular-nums`; sticky thead; keyboard row focus.  
- **Authority chips:** outline + label; **three tones only** (neutral / warn / fail). No emoji. `NOT_COMPUTABLE` always shows reason code.  
- **Provenance:** right-edge sheet (mono key/value, copy hash) — not stacked modals.  
- **Ft4 colophon:** `PAPER_ONLY · capital_authority=false · schema v1 · api :8000 · run_id · build`.  
- **Overview** binds only fields present on the current `OperatorDashboardPacket`; missing → `—` + reason. Never fabricate ROI for empty demo.

### 6.4 Panels (packet-backed)

| Area | Shows | Missing data |
|------|--------|--------------|
| Today / Overview | Fields present on dashboard packet | `—` + reason |
| Today / Actions | Ingest, compete, paper selected, settle, refresh, export | Disabled with precondition reason |
| Book / Candidates | Strategy, selection, score, confidence, features, authority | Fail-closed empty copy |
| Book / Paper | Open/settled tickets, stake, EV, candidate links | Empty ledger, not placeholder P&L |
| Book / Settlement | PENDING queue, WIN/LOSS/PUSH/VOID, outcome source | PENDING stays pending |
| Health / Sources | Registry, last fetch, health, missing fields | FAIL/WARN with reason codes |
| Health / Performance | ROI, hit rate, CLV, max DD, sample, by strategy/league | Exclude PENDING; always show sample size |
| Health / Promotion | Gate checklist, status ladder | Failed gates listed |
| Health / Run log | Packet hashes, run list, export JSON | — |

### 6.5 Interaction states

Every primary control implements: **default · hover · focus-visible · active · disabled · loading · error · success**.

- Loading: delay-show ≥150ms; table skeletons where layout known.  
- Success: **silent** row/panel update (no celebratory toast).  
- Toast only for async failure or invisible effect.  
- Destructive (reset demo ledger): confirm.  
- Motion: cut-first; `transform`/`opacity` only; `prefers-reduced-motion`. No `transition-all`, no card hover-scale.

### 6.6 Responsive

- Primary: ≥1024 desktop workbench.  
- &lt;768: single column; rail → sheet; tables in overflow-x clip container with sticky first column; no two-line button labels.  
- `overflow-x: clip` on `html` and `body`.

### 6.7 Local dev

```text
uvicorn hollersports.api.app:app --reload --port 8000
cd packages/operator-web && npm run dev   # proxy /v1 → :8000
```

---

## 7. Free-first sources (day one)

### 7.1 Roles

| Role | Examples |
|------|----------|
| Truth / schedule / scores | ESPN scoreboard (and league-appropriate fallbacks) |
| Odds | The Odds API free tier (or documented free alternative); multi-book snapshots |
| Context / redundancy | BallDontLie (NBA), API-Sports free quota where useful |
| Splits | Public capture only when available; otherwise NOT_COMPUTABLE for split-dependent strategies |

Paid vendors (Sportradar, SportsDataIO, OddsJam, etc.) are adapter slots for later, not v1 requirements.

### 7.2 Source registry

`sources/registry.yaml` declares for each source: role, tier, adapter module, authority default (`SHADOW_ONLY`), provides/missing capabilities.

Source health evaluates freshness, required fields, provenance presence. FAIL blocks ingestion. WARN may ingest with flag. Health modules never emit recommendations.

---

## 8. Paper portfolio, settlement, promotion

### 8.1 Paper loop

`ExecutionPacket → PaperPortfolioPacket → Settlement → PerformancePacket → PromotionPacket → Operator projection`

Settlement states: `PENDING | WIN | LOSS | PUSH | VOID | NOT_COMPUTABLE`.

Settlement requires final score / market result provenance. Performance metrics **exclude** unresolved PENDING entries.

### 8.2 Promotion gates (defaults; config-tunable)

- `sample_size >= 100` settled  
- `ROI > 0.05`  
- `max_drawdown < 0.20`  
- `CLV_retention >= 0`  
- `source_health` pass rate `>= 0.95`  
- 12-run invariance PASS  
- at least 3 distinct regimes observed  
- at least 3 distinct market types observed  
- no unresolved execution audit blockers  

Statuses: `BLOCKED | WATCH | REVIEW_ELIGIBLE | PROMOTION_RECOMMENDED`.

Promotion **never** authorizes live execution.

---

## 9. Testing and verification

### 9.1 Test pyramid

| Layer | Coverage |
|-------|----------|
| Unit | source_health, strategies, execution_guard, settle, performance, promotion, authority helpers |
| Integration | pipeline ingest→compete→paper→settle; API schema-valid packets |
| Golden | 12-run invariance on fixture slate (identical packet hashes) |
| Authority locks | no packet may set live capital or live execution true |
| UI smoke | Today empty state; Book with fixture candidates; Health sources FAIL path; no Place bet control |
| Schema | every emitted packet validates against `schemas/json/*.v1.schema.json` |

### 9.2 Acceptance behaviors

- Identical inputs produce identical tickets/candidates/hashes  
- Missing odds return NOT_COMPUTABLE  
- Uncalibrated model edge cannot alter pick weights  
- Ticket path cannot grant capital authority  
- Outcome packet path exists for completed paper tickets  
- Dashboard projection cannot mutate ledger authority  

---

## 10. System contract and docs

Ship with:

| Doc | Purpose |
|-----|---------|
| `docs/SYSTEM_CONTRACT.md` | The ten non-negotiable laws (see §1.3 + promotion/settlement rules) |
| `docs/ABRAXAS_LINEAGE.md` | Concept export map; no runtime dependency claim |
| `docs/OPERATOR_RUNBOOK.md` | Daily operator day: fixture mode, live free sources, settle flow |

---

## 11. V1 cut line (shippable when)

- [ ] Unified Python package + FastAPI serving packets  
- [ ] Free-first adapters for day-one leagues + fixture pack for offline day  
- [ ] Source health + MarketIngestionPacket  
- [ ] Three market-first strategies + model-edge registered but gated off  
- [ ] Paper portfolio + settlement + performance + promotion  
- [ ] Next.js Workbench/Cobalt operator (Today · Book · Health) with Hallmark lock  
- [ ] Golden tests + authority lock tests green  
- [ ] SYSTEM_CONTRACT + ABRAXAS_LINEAGE + OPERATOR_RUNBOOK  

---

## 12. Implementation order

1. Repo layout + schemas + governance helpers  
2. Sources + health + fixture pack  
3. Strategies + competition loop  
4. Paper loop (guard → ledger → settle → performance → promotion)  
5. FastAPI  
6. Operator web (tokens → shell → Today → Book → Health)  
7. Golden + authority CI  
8. Docs polish  

Implementation plans are produced separately via the writing-plans skill after this spec is user-approved on disk.

---

## 13. Complexity rent

HollerSports complexity is justified only if it reduces at least one of: pick ambiguity, calibration ambiguity, ticket construction ambiguity, correlation risk, variance misread, post-loss learning failure, time-to-slate decision, operator load.

If a layer pays no measurable rent, it stays SHADOW-only or is archived.

---

## 14. Sources for this design

- GitHub repo `scrimshawlife-ctrl/Hollersports` (engine + hollersports-core skeleton)  
- Notion: HollerSports Runtime; Phase 7 Steps 1–4; Paper Portfolio Loop v3.1; Free-First API Registry; Abraxas integration spine (concept extraction only)  
- Local Abraxas skills: holler-ingest, holler-calibrate, slang-emergence (lineage only; slang not in v1 core path)  
- Hallmark audit of Design §3 (2026-08-04) folded into §6  

---

## Document history

| Date | Change |
|------|--------|
| 2026-08-04 | Initial approved design from brainstorming session |
