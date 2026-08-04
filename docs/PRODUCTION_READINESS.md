# HollerSports production readiness

## Decision model

Production readiness is evaluated against **evidence from an exact source SHA**. It is not inferred from feature completion, local green tests alone, a release-candidate label, or a successful demo.

Readiness states:

- `PASS` — required evidence exists and satisfies the gate.
- `FAIL` — evidence demonstrates the gate is not satisfied.
- `NOT_COMPUTABLE` — required evidence is missing, stale, partial, or inaccessible.
- `WAIVED` — an authorized owner accepts a bounded non-critical risk with rationale and expiry.

**Critical authority, capital, integrity, or security blockers cannot be waived** for a paper-operator production-supported release.

## Two-class product (non-negotiable)

| Class | Meaning | Allowed? |
|-------|---------|----------|
| **PAPER_OPERATOR_READY** | Reproducible paper day (fixture and/or free sources), settle, measure, project dashboard, CI/goldens, documented ops | **Target** |
| **LIVE_CAPITAL_READY** | Live book placement or capital movement via this product | **Forbidden** unless system contract is explicitly rewritten by human review outside the model |

Hard rule: `capital_authority=false`, `execution_authority=false`, execution `mode=PAPER_ONLY`. No live book integration.

See [SYSTEM_CONTRACT.md](SYSTEM_CONTRACT.md).

## Current posture

**Classification:** early alpha / pre–paper-operator GA.  
**Verdict:** **Not PAPER_OPERATOR_READY.**

Feature completion of Tasks 1–6 and green unit tests **do not** establish paper-operator production readiness. FastAPI, operator UI, golden invariance suite, and CI are required for the declared operator product surface.

| Document | Role |
|----------|------|
| [evidence/PRODUCTION_READINESS_MATRIX.md](evidence/PRODUCTION_READINESS_MATRIX.md) | SHA-pinned area scores |
| [evidence/PRODUCTION_READINESS_ASSESSMENT_2026-08-04.md](evidence/PRODUCTION_READINESS_ASSESSMENT_2026-08-04.md) | Dated narrative assessment |
| [atlas/HOLLERSPORTS_ATLAS.md](atlas/HOLLERSPORTS_ATLAS.md) | OBSERVED vs PLANNED topology |
| [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md) | Fixture operator day |

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

To advance readiness: land Phase B (goldens → API → Workbench → CI → packaging → smoke), then rewrite assessment at the freeze SHA.
