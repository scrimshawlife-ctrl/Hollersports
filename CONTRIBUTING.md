# Contributing to HollerSports

Thank you for helping. This repo is an **advisory-only** sports market intelligence operator. Contributions must respect the product law.

## Product law (non-negotiable)

- No real money, wallets, payments, or capital custody
- No sportsbook placement or live execution paths
- `capital_authority` and `execution_authority` remain **false**
- Prefer offline `fixtures/` for CI; free-first network is optional and still advisory
- Fail closed — do not invent odds, lines, or model probabilities
- Do not invent metrics or testimonials in docs

Full laws: [docs/SYSTEM_CONTRACT.md](docs/SYSTEM_CONTRACT.md).

## Prerequisites

| Tool | Version |
|------|---------|
| Python | ≥ 3.11 |
| Node | ≥ 20 (Workbench only) |
| Make | optional but preferred |

```bash
git clone https://github.com/scrimshawlife-ctrl/Hollersports.git
cd Hollersports
python3 -m venv .venv && source .venv/bin/activate
```

## Local setup

```bash
# Python package + tests
make install
make test
make smoke

# Full local gate used before merge
make validate

# Field-test freeze receipt (offline ML path included)
make field-test

# Workbench (optional)
make api   # :8000
make web   # :3000 — needs npm install in packages/operator-web once
```

Optional extras:

```bash
pip install -e "packages/hollersports[ml]"       # sklearn HGB
pip install -e "packages/hollersports[torch]"    # axial / transformer presets
pip install -e "packages/hollersports[research]" # ml + torch
```

## Branch & PR workflow

1. Branch from `main` (or from `v0.5.0-advisory-beta` only for freeze-pin demos — prefer feature branches off `main` for code changes).
2. Keep PRs focused: one track or surface when possible.
3. Run `make validate` (and `cd packages/operator-web && npm run build` if you touch the Workbench).
4. Update docs when behavior or surfaces change:
   - [docs/atlas/HOLLERSPORTS_ATLAS.md](docs/atlas/HOLLERSPORTS_ATLAS.md) for topology
   - [docs/README.md](docs/README.md) index if new canonical docs appear
   - [docs/RELEASE_NOTES.md](docs/RELEASE_NOTES.md) for user-visible releases
5. Never claim money rails, multi-tenant GA, or invented performance numbers.

### PR checklist

- [ ] `make validate` green (or equivalent pytest + smoke)
- [ ] Workbench build green if `packages/operator-web` changed
- [ ] No secrets committed
- [ ] Authority seals unchanged unless the PR is an explicit contract rewrite (requires human approval)
- [ ] Docs honesty: OBSERVED vs PLANNED; no invented metrics
- [ ] Evidence receipts only under `docs/evidence/` as run outputs

## Code layout (where to edit)

| Change type | Primary paths |
|-------------|----------------|
| Kernel / strategies / paper | `packages/hollersports/hollersports/` |
| HTTP API | `packages/hollersports/hollersports/api/` |
| Research ML | `packages/hollersports/hollersports/ml/` · `scripts/holler/` |
| Workbench UI | `packages/operator-web/` · root [design.md](design.md) |
| Contracts | `schemas/json/` · packet models under `hollersports/schemas/` |
| Fixtures | `fixtures/day00N/` · `fixtures/MANIFEST.json` |
| Agent playbooks | `docs/agents/` · [AGENTS.md](AGENTS.md) |

Legacy `engine/` and `hollersports-core/` are **not** the operator path — see [docs/MIGRATION_ENGINE.md](docs/MIGRATION_ENGINE.md).

## Tests

| Layer | Command |
|-------|---------|
| All (ignore legacy core) | `make test` |
| Unit | `make test-unit` |
| Integration | `make test-integration` |
| Golden | `make test-golden` |
| Calibration | `make test-calibration` |
| Coverage | `make test-cov` |

Details: [docs/TESTING_AND_CALIBRATION.md](docs/TESTING_AND_CALIBRATION.md).

## Freeze policy

Field testing pins **`v0.5.0-advisory-beta`**. Large transformer expansion is deferred ([docs/TRACK_F_FUTURE_TRANSFORMERS.md](docs/TRACK_F_FUTURE_TRANSFORMERS.md)). Do not unfreeze model scale work without an explicit product decision.

## License

By contributing, you agree that your contributions are licensed under the Apache License 2.0 — see [LICENSE](LICENSE).
