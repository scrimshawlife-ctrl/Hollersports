# Production readiness matrix

```yaml
product: hollersports
class_target: PAPER_OPERATOR_READY
assessed_sha: 2890bc931341ad04ae10ccacaec6fc883a652242
branch: feature/hollersports-standalone-operator
package_version: "0.2.0"
date: "2026-08-04"
tests:
  command: "pytest tests/ --ignore=hollersports-core -q"
  result: "34 passed"
full_narrative: PRODUCTION_READINESS_ASSESSMENT_2026-08-04.md
```

## Gate scores

| Gate | Area | State | Evidence |
|------|------|--------|----------|
| G0 | Scope freeze | **FAIL** | Feature branch only; no RC tag; main not freeze SHA |
| G1 | Product journey | **FAIL** | `run_operator_day` library path only; no API/UI |
| G2 | Authority / capital | **PASS*** | Runtime asserts; *no dedicated golden lock suite yet |
| G3 | Determinism | **NOT_COMPUTABLE** | No 12-run golden tests |
| G4 | Packet contracts | **PASS** | `schemas/json/` + `tests/unit/test_packets.py` |
| G5 | Fail-closed ingest | **PASS** | Health/ingest + tests; fail-path coverage thin |
| G6 | Paper ledger | **PASS** | `tests/unit/test_paper_ledger.py` |
| G7 | Settlement / promotion | **PASS** | Settlement + promotion unit/integration |
| G8 | CI | **FAIL** | No `.github/workflows` |
| G9 | Packaging | **FAIL** | Editable install works; registry package-data risk |
| G10 | Ops | **PASS** | Runbook draft; no smoke receipt artifact yet |
| G11 | Security | **NOT_COMPUTABLE** | No secret-scan CI; no live keys path |
| G12 | Docs honesty | **PASS** | README + atlas OBSERVED/PLANNED |
| G13 | Hosting / multi-user | **WAIVED** | Local single-operator v1 by design |
| G14 | Live capital | **PASS** | Forbidden by contract + code |

## Summary counts

| State | Count |
|-------|-------|
| PASS | 6 (+ G2 provisional) |
| FAIL | 4 |
| NOT_COMPUTABLE | 2 |
| WAIVED | 1 |
| PASS-as-forbidden (G14) | 1 |

**Aggregate:** not PAPER_OPERATOR_READY.
