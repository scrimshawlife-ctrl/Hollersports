# HollerSports production readiness

## Decision model

Production readiness is evaluated against **evidence from an exact source SHA**. It is not inferred from feature completion, local green tests alone, a release-candidate label, or a successful demo.

Readiness states:

- `PASS` — required evidence exists and satisfies the gate.
- `FAIL` — evidence demonstrates the gate is not satisfied.
- `NOT_COMPUTABLE` — required evidence is missing, stale, partial, or inaccessible.
- `WAIVED` — an authorized owner accepts a bounded non-critical risk with rationale and expiry.

**Critical authority, capital, integrity, or security blockers cannot be waived** for a paper-operator production-supported release.

## Product class (non-negotiable)

HollerSports is **betting advice only**. It does **not** handle real money.

| Class | Meaning | Allowed? |
|-------|---------|----------|
| **ADVISORY_OPERATOR_READY** (aka paper operator ready) | Reproducible advisory day: ingest → candidates → paper simulation of advice quality → settle/score → dashboard; CI/goldens; documented ops | **Target** |
| **MONEY_OR_LIVE_BOOK_READY** | Wallets, payments, book placement, capital custody or movement | **Forbidden** — not a readiness goal |

Hard rule: no real money, no live book placement. Packet flags stay `capital_authority=false`, `execution_authority=false`, `mode=PAPER_ONLY` (simulation of advised tickets).

See [SYSTEM_CONTRACT.md](SYSTEM_CONTRACT.md).

## Current posture

**Classification:** **local advisory beta** on `main`.  
**Foundation merge:** PR **#3** → `838ea88` (2026-08-04) — **MERGED** (no open PR remains).  
**Tip SHA:** `aa89903` (continuum on `main`; package **0.3.0**, tag `v0.3.0-advisory-beta`).  
**Verdict:** **PASS** for local **ADVISORY_OPERATOR_READY** (no real money, no book placement).  
**Not claimed:** multi-tenant SaaS GA, hosted multi-user production, any money rail.

| Document | Role |
|----------|------|
| [evidence/PRODUCTION_READINESS_CONTINUUM_2026-08-04.md](evidence/PRODUCTION_READINESS_CONTINUUM_2026-08-04.md) | Tip continuum after PR #3 (this board’s current pin) |
| [evidence/PRODUCTION_READINESS_MATRIX.md](evidence/PRODUCTION_READINESS_MATRIX.md) | Foundation matrix @ PR #3 merge SHA |
| [evidence/PRODUCTION_READINESS_ASSESSMENT_2026-08-04-post-merge.md](evidence/PRODUCTION_READINESS_ASSESSMENT_2026-08-04-post-merge.md) | Post-merge PASS (local advisory beta) |
| [evidence/PRODUCTION_READINESS_ASSESSMENT_2026-08-04.md](evidence/PRODUCTION_READINESS_ASSESSMENT_2026-08-04.md) | Baseline pre Phase B (NOT READY) |
| [evidence/PRODUCTION_READINESS_DELTA_2026-08-04-phase-b.md](evidence/PRODUCTION_READINESS_DELTA_2026-08-04-phase-b.md) | Phase B delta |
| [evidence/smoke_operator_day.last.json](evidence/smoke_operator_day.last.json) | Fixture smoke receipt |
| [evidence/calibration_suite.last.json](evidence/calibration_suite.last.json) | Multi-fixture calibration receipt |
| [atlas/HOLLERSPORTS_ATLAS.md](atlas/HOLLERSPORTS_ATLAS.md) | OBSERVED topology |
| [agents/HERMES_BACKFILL.md](agents/HERMES_BACKFILL.md) | Agent backfill playbook |
| [MIGRATION_ENGINE.md](MIGRATION_ENGINE.md) | Legacy engine notes |
| [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md) | Fixture operator day |
| [TESTING_AND_CALIBRATION.md](TESTING_AND_CALIBRATION.md) | Test layers + calibration ladder |

## Maturity ladder

| Level | Definition |
|-------|------------|
| **Development** | Partial library; fixtures; no support promise |
| **Alpha** | Library closed loop + honesty docs; engineering evaluation |
| **Paper beta** | API + Workbench + CI + goldens; controlled operator validation |
| **PAPER_OPERATOR_READY** | Explicit release decision + SHA pin + smoke receipt |
| **Live capital** | Not on this ladder |

## Gates (G0–G14)

| ID | Area | Required evidence |
|----|------|-------------------|
| G0 | Scope freeze | Declared release scope; branch/main policy; tag intent |
| G1 | Product journey | Operator day path (API and/or Workbench) complete for declared scope |
| G2 | Authority / capital | No live path; golden locks; grep seals |
| G3 | Determinism | 12-run fixture invariance |
| G4 | Packet contracts | Schemas + validation tests |
| G5 | Fail-closed ingest | Source health FAIL/WARN/NC + reject paths tested |
| G6 | Paper ledger | Hash chain tests; documented data root |
| G7 | Settlement / promotion | Tests; promotion never live |
| G8 | CI | Required workflow on PR/main |
| G9 | Packaging | Installable package; package-data for registry |
| G10 | Ops | Runbook + one-command smoke + evidence receipt |
| G11 | Security | No secrets in tree; response authority seals |
| G12 | Docs honesty | README/atlas match OBSERVED/PLANNED |
| G13 | Hosting / multi-user | WAIVED for local single-operator v1 |
| G14 | Live capital | Must remain **PASS-as-forbidden** |

## Release decision template

```yaml
release_decision:
  product: hollersports
  class: PAPER_OPERATOR_READY  # never LIVE_CAPITAL_READY without contract rewrite
  version: null
  sha: null
  mode: PAPER_ONLY
  capital_authority: false
  execution_authority: false
  smoke_receipt: null  # path under docs/evidence/
  verdict: NOT_READY  # PASS | NOT_READY
  owner: null
  date: null
```

## Continuity

Phase B and PR #3 foundation are **done** (merged). Continuum after merge (model edge, calibration bank, Hermes backfill, day002, testing framework) is on `main` @ tip — see [evidence/PRODUCTION_READINESS_CONTINUUM_2026-08-04.md](evidence/PRODUCTION_READINESS_CONTINUUM_2026-08-04.md).

To re-pin a formal freeze: cut a tag at tip, refresh smoke + calibration suite receipts, update continuum `tip_sha`.
