# Legacy engine / core migration notes

## Primary path (current)

All new work lives under:

```text
packages/hollersports/hollersports/   # library + API
packages/operator-web/                # advisory Workbench UI
schemas/json/                         # packet contracts
fixtures/                             # offline day packs
```

Install: `pip install -e "packages/hollersports[dev]"`  
Run: `make validate` · `make api` · `make web`

Product law: **advisory only — no real money, no book placement.**

## Legacy trees (kept for reference)

| Path | Role | Status |
|------|------|--------|
| `engine/` | Original slate isolation + Monte Carlo picks | **Legacy** — do not extend for operator features |
| `hollersports-core/` | Feedback loop / prior updates sketch | **Legacy** — ideas may inform future model-edge calibration |
| `INTEGRATION_GUIDE.md` | Documents old `SlateRunner` wiring | Historical |

## Migration policy

1. **Do not** add new operator features to `engine/` or `hollersports-core/`.
2. Prefer ports into `packages/hollersports` (governance, packets, paper loop).
3. Model-edge Monte Carlo (if enabled later) should wrap as `MODEL_PROBABILITY_EDGE` behind calibration gates — never bypass paper/advisory authority.
4. Root `tests/test_state_isolation.py` exercises legacy `engine/`; primary CI is `tests/` under unit/integration/golden for the new package.

## Optional future relocation

Moving `engine/` into `packages/hollersports/hollersports/engine/` with root shims is allowed when:

- Legacy tests are re-homed or green via shims  
- No public import break is required for external consumers  

Not required for advisory operator GA.

## Related

- [atlas/HOLLERSPORTS_ATLAS.md](atlas/HOLLERSPORTS_ATLAS.md)
- [SYSTEM_CONTRACT.md](SYSTEM_CONTRACT.md)
- [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)
