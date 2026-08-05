# Production readiness matrix

```yaml
product: hollersports
class_target: ADVISORY_OPERATOR_READY
# Foundation freeze (historical pin — do not rewrite scores without re-run)
assessed_sha: 838ea88d0aa85b1c85f810bb080c590f5c8a7804
branch: main
package_version: "0.2.0"   # at foundation merge; tip is 0.3.0
date: "2026-08-04"
merged_pr: 3
pr_state: MERGED
tests:
  command: "pytest tests/ --ignore=hollersports-core -q"
  result: "43 passed"   # at foundation; tip ~101 passed
smoke:
  command: "python scripts/smoke_operator_day.py"
  receipt: docs/evidence/smoke_operator_day.last.json
full_narrative: PRODUCTION_READINESS_ASSESSMENT_2026-08-04-post-merge.md
continuum: PRODUCTION_READINESS_CONTINUUM_2026-08-04.md
prior: PRODUCTION_READINESS_ASSESSMENT_2026-08-04.md
delta: PRODUCTION_READINESS_DELTA_2026-08-04-phase-b.md
```

> **Current tip** (post-merge continuum): see [PRODUCTION_READINESS_CONTINUUM_2026-08-04.md](PRODUCTION_READINESS_CONTINUUM_2026-08-04.md) (`96ffd8a`, package 0.3.0). Gate table below is the **PR #3 foundation** pin.

## Gate scores

| Gate | Area | State | Evidence |
|------|------|--------|----------|
| G0 | Scope freeze | **PASS** | PR #3 merged to `main` @ `838ea88` |
| G1 | Product journey | **PASS** | API + Workbench + `run_operator_day` |
| G2 | Authority / capital | **PASS** | Goldens; no money path |
| G3 | Determinism | **PASS** | `tests/golden/test_12_run_invariance.py` |
| G4 | Packet contracts | **PASS** | schemas + unit tests |
| G5 | Fail-closed ingest | **PASS** | FAIL/WARN/NC unit coverage |
| G6 | Paper ledger | **PASS** | simulation metrics only |
| G7 | Settlement / promotion | **PASS** | advice quality scoring |
| G8 | CI | **PASS** | `.github/workflows/ci.yml` green on PR |
| G9 | Packaging | **PASS** | package-data + editable install |
| G10 | Ops | **PASS** | Makefile + smoke receipt |
| G11 | Security | **PASS** | no secrets path; authority seals |
| G12 | Docs honesty | **PASS** | advisory-only |
| G13 | Hosting / multi-user | **WAIVED** | local single-operator v1 |
| G14 | Money / live books | **PASS** | forbidden by contract |

## Aggregate

**Local advisory beta: PASS.**  
**Money / live books: never.**  
**SaaS multi-tenant GA: not claimed.**
