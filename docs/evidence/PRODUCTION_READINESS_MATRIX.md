# Production readiness matrix

```yaml
product: hollersports
class_target: PAPER_OPERATOR_READY
# Pin after commit lands; re-run make validate to refresh smoke
assessed_sha: 2e8dfada81d8646b3a7e849f8569a2da9273e786
branch: feature/hollersports-standalone-operator
package_version: "0.2.0"
date: "2026-08-04"
tests:
  command: "pytest tests/ --ignore=hollersports-core -q"
  result: "38 passed"
smoke:
  command: "python scripts/smoke_operator_day.py"
  receipt: docs/evidence/smoke_operator_day.last.json
  core_hash: d57753edccd568d77d81ea6cc573d9a734de8fe023164f7e681d514ff7f65921
full_narrative: PRODUCTION_READINESS_ASSESSMENT_2026-08-04.md
delta: PRODUCTION_READINESS_DELTA_2026-08-04-phase-b.md
```

## Gate scores

| Gate | Area | State | Evidence |
|------|------|--------|----------|
| G0 | Scope freeze | **FAIL** | Feature branch; not merged/tagged as RC |
| G1 | Product journey | **PASS** | API + Workbench + `run_operator_day` |
| G2 | Authority / capital | **PASS** | Goldens + API `_safe_packet` + UI grep |
| G3 | Determinism | **PASS** | `tests/golden/test_12_run_invariance.py` |
| G4 | Packet contracts | **PASS** | schemas + unit tests |
| G5 | Fail-closed ingest | **PASS** | health/ingest (fail-path still thin) |
| G6 | Paper ledger | **PASS** | unit + smoke |
| G7 | Settlement / promotion | **PASS** | unit/integration |
| G8 | CI | **PASS*** | `.github/workflows/ci.yml` present (*green on remote after push) |
| G9 | Packaging | **PASS** | package-data for registry.yaml; editable install |
| G10 | Ops | **PASS** | runbook + Makefile + smoke receipt |
| G11 | Security | **PASS** | no live keys; authority seals; local-only |
| G12 | Docs honesty | **PASS** | README/atlas/board |
| G13 | Hosting / multi-user | **WAIVED** | local single-operator v1 |
| G14 | Live capital | **PASS** | forbidden |

## Summary counts

| State | Count |
|-------|-------|
| PASS | 12 (G8 provisional until first remote CI) |
| FAIL | 1 (G0) |
| WAIVED | 1 |
| PASS-as-forbidden (G14) | counted in PASS |

**Aggregate:** **not PAPER_OPERATOR_READY** until G0 (merge/tag + release decision). Local paper beta bar is largely met.
