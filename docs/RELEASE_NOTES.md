# HollerSports release notes

Advisory-only product. No real money, no book placement, no capital custody.

## Merge status

| Span | State | Notes |
|------|--------|--------|
| **#3** — standalone advisory operator | **MERGED** `838ea88` | Foundation local advisory beta |
| **#4–#11** | **MERGED** on `main` | Free-first, settle, calibration bank continuum |
| **#12–#17** — Track F research ML | **MERGED** | Features → train → EV → axial/RSS → gated retrain |

---

## v0.4.0-advisory-beta (package 0.4.0)

**Tag:** `v0.4.0-advisory-beta`  
**Tip:** `a10468d` on `main` (PR #17 merge)  
**Theme:** Track F research ML pipeline on top of the v0.3 advisory operator.

### Highlights

- Offline **features → L2 logistic** (optional sklearn HGB) → **temperature ensemble** → EV annotate into `model_probability` for gated `MODEL_PROBABILITY_EDGE`
- **API** `/v1/ml/*`: train, annotate, status, retrain-check, retrain-apply (confirm required), model-card, axial, RSS sentiment
- **Workbench Health:** Research ML panel (train / annotate+compete / retrain check)
- **Free-first odds movement:** cross-book `odds_history` / `odds_delta` + temporal snapshots under `data_root/ml/`
- **Sentiment:** offline lexicon + optional **RSS/Atom** inject or HTTPS fetch (ESPN sports defaults, cached)
- **Model cards:** auto on train, `scripts/holler/doc_model.py`, `GET /v1/ml/model-card`
- **Axial models:** stdlib stub + optional **PyTorch** factorized attention (`[torch]` / `make ml-axial-train` / `POST /v1/ml/axial`)
- **Hermes:** `docs/agents/HERMES_ML.md` + `make ml-e2e` / `ml-compete` / `ml-retrain-check`

### Authority (unchanged)

| Flag | Value |
|------|--------|
| Mode | `ADVISORY_ONLY` / `PAPER_ONLY` |
| `capital_authority` | always false |
| `execution_authority` | always false |
| Live books | disabled |
| Auto-retrain | never silent — `confirm=true` required |

### Optional installs

```bash
pip install -e "packages/hollersports[dev]"       # CI default
pip install -e "packages/hollersports[ml]"        # sklearn HGB
pip install -e "packages/hollersports[torch]"     # axial PyTorch
pip install -e "packages/hollersports[research]"  # ml + torch
```

### Verify

```bash
pip install -e "packages/hollersports[dev]"
pytest tests/ --ignore=hollersports-core
make smoke
make ml-e2e          # offline ML path; asserts model-edge candidates
make api && make web
```

### Not in this release

- Real-money execution or sportsbook placement
- Multi-tenant SaaS / auth
- PyPI publish
- Production-scale transformers (see research notes below)
- Twitter/X or paid social firehose (RSS only for live text)
- Full Monte Carlo / legacy `engine/` as operator default

### PRs in this tag (Track F)

| PR | Title |
|----|--------|
| #12 | Track F research ML pipeline (CLI + API + Workbench) |
| #13 | ML retrain-check API + offline sentiment |
| #14 | Model cards + axial temporal stub |
| #15 | Gated ML retrain-apply |
| #16 | PyTorch axial temporal model |
| #17 | RSS sentiment feeds |

---

## v0.3.0-advisory-beta (package 0.3.0)

**Tag:** `v0.3.0-advisory-beta`  
**Foundation:** PR #3 merge  
**Tip (docs pin at cut):** continuum free-first closed day on `main`

### Product

- Standalone `packages/hollersports` operator + Cobalt Workbench (`packages/operator-web`)
- Closed paper loop: fixture / free-first observe → candidates → paper simulation → settle → performance / promotion review
- Free-first ESPN + The Odds API observation (keys optional; CI uses injection)
- Free-first multi-league observe + multi-ingest auto-compete
- Fixtures `day001` + `day002` + `day003`
- Advice reliability buckets + history; calibration ladder; settlement bank + Hermes backfill
- Free-first closed day CLI / API / Workbench
- Testing framework: pytest markers, calibration suite, CI

### Authority

| Flag | Value |
|------|--------|
| Mode | `ADVISORY_ONLY` / `PAPER_ONLY` |
| `capital_authority` | always false |
| `execution_authority` | always false |
| Live books | disabled |

### Operator surface

| Surface | Notes |
|---------|--------|
| Today | Fixture select, full day, free-first, compete/paper/settle |
| Book | Paper portfolio projection |
| Health | Sources, performance, promotion, calibration, reliability |

### Agent / Hermes

| Path | Role |
|------|------|
| `AGENTS.md` | Repo agent entry |
| `docs/agents/HERMES_BACKFILL.md` | Backfill playbook |
| `scripts/backfill_status.py` | `needs_backfill` + suggested command |
| `make backfill` | Multi-fixture accumulation |

### Verify locally

```bash
pip install -e "packages/hollersports[dev]"
pytest tests/ --ignore=hollersports-core
make smoke
make calibration-suite
make backfill-status
make api   # :8000
make web   # Workbench
```

See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md), [SYSTEM_CONTRACT.md](SYSTEM_CONTRACT.md), [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md), [TESTING_AND_CALIBRATION.md](TESTING_AND_CALIBRATION.md).
