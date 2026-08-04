# HollerSports release notes

Advisory-only product. No real money, no book placement, no capital custody.

## Merge status

| PR | State | Notes |
|----|--------|--------|
| **#3** — standalone advisory operator | **MERGED** `838ea88` | Foundation local advisory beta |
| Subsequent continuum | on `main` (no open PR) | Calibration, backfill, Hermes docs — tip `3feb5e4` |

---

## v0.3.0-advisory-beta (package 0.3.0)

**Tag:** `v0.3.0-advisory-beta`  
**Foundation:** PR #3 merge  
**Tip (docs pin):** `4a91728` on `main`

### Product

- Standalone `packages/hollersports` operator + Cobalt Workbench (`packages/operator-web`)
- Closed paper loop: fixture / free-first observe → candidates → paper sim → settle → performance / promotion review
- Free-first ESPN + The Odds API observation (keys optional; CI uses injection)
- Multi-sport ESPN day-one surface (NBA / NFL / MLB / NHL / EPL / MLS)
- Fixtures `day001` + `day002` (model fields)
- Advice reliability buckets + append-only reliability history + Workbench tables
- Gated `MODEL_PROBABILITY_EDGE` (deterministic market fields; calibration-gated)
- Calibration ladder (`CalibrationPacket.v1`): EMPTY → UNRELIABLE → WATCH → RELIABLE
- Cumulative settlement bank + `make backfill` / Hermes status CLI
- Testing framework: pytest markers, calibration suite, CI backfill step

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
| Today | Fixture select, full day, free-first, compete/paper/settle; model-edge opt-in (auto-cal) |
| Book | Paper portfolio projection |
| Health | Sources, performance, promotion, **calibration**, reliability buckets + history |

### Agent / Hermes

| Path | Role |
|------|------|
| `AGENTS.md` | Repo agent entry |
| `docs/agents/HERMES_BACKFILL.md` | Backfill playbook |
| `scripts/backfill_status.py` | `needs_backfill` + suggested command |
| `make backfill` | Multi-fixture accumulation |

### Not in this release

- Real-money execution or sportsbook placement
- Multi-tenant SaaS / auth
- PyPI publish
- Full Monte Carlo / legacy `engine/` as operator default
- Vercel hosted deploy (deferred; local-first)

### Verify locally

```bash
pip install -e "packages/hollersports[dev]"
pytest tests/ --ignore=hollersports-core   # ~101 tests
make smoke
make calibration-suite
make backfill-status
make api   # :8000
make web   # Workbench
```

See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md), [SYSTEM_CONTRACT.md](SYSTEM_CONTRACT.md), [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md), [TESTING_AND_CALIBRATION.md](TESTING_AND_CALIBRATION.md).
