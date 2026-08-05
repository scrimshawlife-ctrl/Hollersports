# Agent playbooks (HollerSports)

Index for Hermes and other agents working this repo.

| Task | Playbook | First command |
|------|----------|----------------|
| **Fixture paper backfill / calibration sample** | [HERMES_BACKFILL.md](HERMES_BACKFILL.md) | `python scripts/backfill_status.py` |
| **Track F ML (features→train→EV→model edge)** | [HERMES_ML.md](HERMES_ML.md) | `make ml-e2e` |
| Testing & calibration ladder | [../TESTING_AND_CALIBRATION.md](../TESTING_AND_CALIBRATION.md) | `make test-calibration` |
| Human operator day | [../OPERATOR_RUNBOOK.md](../OPERATOR_RUNBOOK.md) | `make api` · `make web` |
| Nightly notes | [../BACKFILL_AND_NIGHTLY.md](../BACKFILL_AND_NIGHTLY.md) | `make backfill` |

**Product law (all agents):** never real money, never live books, never set capital/execution authority true.
