# Agent playbooks (HollerSports)

Index for Hermes and other agents working this repo.

| Task | Playbook | First command |
|------|----------|----------------|
| **v0.4 field-test freeze (small ML)** | [../TRACK_F_FREEZE_AND_FIELD_TEST.md](../TRACK_F_FREEZE_AND_FIELD_TEST.md) | `git checkout v0.4.0-advisory-beta` · `make ml-e2e` |
| **Fixture paper backfill / calibration sample** | [HERMES_BACKFILL.md](HERMES_BACKFILL.md) | `python scripts/backfill_status.py` |
| **Track F ML (features→train→EV→model edge)** | [HERMES_ML.md](HERMES_ML.md) | `make ml-e2e` |
| Future large transformers (deferred) | [../TRACK_F_FUTURE_TRANSFORMERS.md](../TRACK_F_FUTURE_TRANSFORMERS.md) | Unfreeze first |
| Testing & calibration ladder | [../TESTING_AND_CALIBRATION.md](../TESTING_AND_CALIBRATION.md) | `make test-calibration` |
| Human operator day | [../OPERATOR_RUNBOOK.md](../OPERATOR_RUNBOOK.md) | `make api` · `make web` |
| Nightly notes | [../BACKFILL_AND_NIGHTLY.md](../BACKFILL_AND_NIGHTLY.md) | `make backfill` |

**Product law (all agents):** never real money, never live books, never set capital/execution authority true.
