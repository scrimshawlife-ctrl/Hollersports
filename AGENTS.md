# Agent instructions — HollerSports

Local **advisory-only** sports market intelligence. No real money. No book placement.

## Start here

| Goal | Open | Run |
|------|------|-----|
| **Backfill paper settlements (calibration sample)** | [`docs/agents/HERMES_BACKFILL.md`](docs/agents/HERMES_BACKFILL.md) | `python scripts/backfill_status.py` then `make backfill` |
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

## Layout (short)

```
packages/hollersports/   # Python kernel + FastAPI
packages/operator-web/   # Next Workbench
fixtures/day00N/         # Offline operator days
scripts/backfill_*.py    # Status + multi-day accumulation
data/backfill/            # Local cumulative bank (gitignored)
docs/agents/             # Agent playbooks
```
