# HollerSports release notes

Advisory-only product. No real money, no book placement, no capital custody.

## v0.3.0-advisory-beta (package 0.3.0)

**Tag:** `v0.3.0-advisory-beta` · **Branch tip after gap close:** includes model-edge + reliability history.

### Product

- Standalone `packages/hollersports` operator + Cobalt Workbench (`packages/operator-web`)
- Closed paper loop: fixture / free-first observe → candidates → paper sim → settle → performance / promotion review
- Free-first ESPN + The Odds API observation (keys optional; CI uses injection)
- Multi-sport ESPN day-one surface (NBA / NFL / MLB / NHL / EPL / MLS)
- Advice reliability buckets on Health; append-only reliability history ledger + Workbench history table
- Gated `MODEL_PROBABILITY_EDGE` (deterministic market fields; off unless calibration allows)

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
| Today | Full fixture day, free-first observe, compete / paper |
| Book | Paper portfolio projection |
| Health | Sources, performance, promotion gates, reliability buckets + history |

### Not in this release

- Real-money execution or sportsbook placement
- Multi-tenant SaaS / auth
- PyPI publish
- Full Monte Carlo / legacy `engine/` as operator default

### Verify locally

```bash
pip install -e "packages/hollersports[dev]"
pytest tests/ --ignore=hollersports-core
make api   # :8000
make web   # Workbench
```

See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md), [SYSTEM_CONTRACT.md](SYSTEM_CONTRACT.md), [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md).
