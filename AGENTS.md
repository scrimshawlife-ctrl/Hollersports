# Agent instructions — HollerSports

Local **advisory-only** sports market intelligence. No real money. No book placement.

## Start here

| Goal | Open | Run |
|------|------|-----|
| **Field-test freeze (after Track G → v0.5)** | [`docs/TRACK_F_FREEZE_AND_FIELD_TEST.md`](docs/TRACK_F_FREEZE_AND_FIELD_TEST.md) | `git checkout v0.5.0-advisory-beta` · `make smoke` · `make ml-e2e` |
| **Backfill paper settlements (calibration sample)** | [`docs/agents/HERMES_BACKFILL.md`](docs/agents/HERMES_BACKFILL.md) | `python scripts/backfill_status.py` then `make backfill` |
| **Track F ML pipeline (features→train→calibrate→EV)** | [`docs/agents/HERMES_ML.md`](docs/agents/HERMES_ML.md) | `make ml-e2e` · `make ml-compete` |
| **Future large transformers (deferred)** | [`docs/TRACK_F_FUTURE_TRANSFORMERS.md`](docs/TRACK_F_FUTURE_TRANSFORMERS.md) | Do **not** start unless unfrozen |
| Agent playbook index | [`docs/agents/README.md`](docs/agents/README.md) | — |
| Fixture inventory | [`fixtures/MANIFEST.json`](fixtures/MANIFEST.json) | — |
| Full test/calibration docs | [`docs/TESTING_AND_CALIBRATION.md`](docs/TESTING_AND_CALIBRATION.md) | `make test` |

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

## Layout (short)

```
packages/hollersports/   # Python kernel + FastAPI
packages/operator-web/   # Next Workbench
fixtures/day00N/         # Offline operator days
scripts/backfill_*.py    # Status + multi-day accumulation
data/backfill/            # Local cumulative bank (gitignored)
docs/agents/             # Agent playbooks
```
