# Agent instructions — HollerSports

Local **advisory-only** sports market intelligence. No real money. No book placement.

## Start here

| Goal | Open | Run |
|------|------|-----|
| **Docs map** | [`docs/README.md`](docs/README.md) | — |
| **Field-test freeze (v0.5 F+G)** | [`docs/TRACK_F_FREEZE_AND_FIELD_TEST.md`](docs/TRACK_F_FREEZE_AND_FIELD_TEST.md) | `git checkout v0.5.0-advisory-beta` · `make field-test` |
| **Backfill paper settlements** | [`docs/agents/HERMES_BACKFILL.md`](docs/agents/HERMES_BACKFILL.md) | `python scripts/backfill_status.py` then `make backfill` |
| **Track F ML pipeline** | [`docs/agents/HERMES_ML.md`](docs/agents/HERMES_ML.md) | `make ml-e2e` · `make ml-compete` |
| **Future large transformers (deferred)** | [`docs/TRACK_F_FUTURE_TRANSFORMERS.md`](docs/TRACK_F_FUTURE_TRANSFORMERS.md) | Do **not** start unless unfrozen |
| **Workbench UI system** | [`design.md`](design.md) · [`packages/operator-web/README.md`](packages/operator-web/README.md) | `make api` · `make web` |
| Agent playbook index | [`docs/agents/README.md`](docs/agents/README.md) | — |
| Fixture inventory | [`fixtures/MANIFEST.json`](fixtures/MANIFEST.json) | — |
| Full test/calibration docs | [`docs/TESTING_AND_CALIBRATION.md`](docs/TESTING_AND_CALIBRATION.md) | `make test` |
| Topology | [`docs/atlas/HOLLERSPORTS_ATLAS.md`](docs/atlas/HOLLERSPORTS_ATLAS.md) | — |

## Hermes backfill (copy-paste)

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python scripts/backfill_status.py          # what needs backfill?
.venv/bin/python -m pip install -e "packages/hollersports[dev]" -q
make backfill                                        # or suggested_command from status
.venv/bin/python scripts/backfill_status.py --assert-min-sample 20
```

Canonical playbook: **`docs/agents/HERMES_BACKFILL.md`**.

## Hard laws

1. `capital_authority` and `execution_authority` always false  
2. No sportsbook placement, wallets, or payments  
3. Prefer offline `fixtures/` over live free-first unless asked  
4. Fail closed — do not invent odds or model probabilities  
5. **Freeze after v0.5:** field-test the shipped F+G stack; do not add money rails or silent retrain ([TRACK_F_FREEZE_AND_FIELD_TEST.md](docs/TRACK_F_FREEZE_AND_FIELD_TEST.md))  
6. **Docs honesty:** no invented metrics; update atlas when surfaces change  

## Layout (short)

```text
packages/hollersports/   # Python kernel + FastAPI + ml/
packages/operator-web/   # Next Workbench (Cobalt)
fixtures/day00N/         # Offline operator days
scripts/holler/          # Track F/G CLI
scripts/backfill_*.py    # Status + multi-day accumulation
data/backfill/           # Local cumulative bank (gitignored)
docs/                    # Index at docs/README.md
docs/agents/             # Agent playbooks
design.md                # Locked Workbench design system
```

## Default validation

```bash
make validate     # install + tests + smoke + calibration suite
make field-test   # smoke + ml-e2e + freeze receipt
```
