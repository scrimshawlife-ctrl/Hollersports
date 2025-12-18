# HollerSports Core — Feedback Loop
This module adds deterministic post-game feedback:
- Ingest `ExpectedOutcome` and `GameResult`
- Compute residuals + variance delta
- Update `ModelState` priors: `fatigue_weight`, `tempo_bias`, `streak_compression`
- Append-only ledgers with provenance hash chain

## Run
python -m hollersports_core.feedback.cli \
  --expected path/to/expected.json \
  --result path/to/result.json \
  --state path/to/state.json \
  --ledger_dir path/to/ledgers
