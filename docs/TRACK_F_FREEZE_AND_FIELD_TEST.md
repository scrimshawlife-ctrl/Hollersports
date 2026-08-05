# Release freeze — test after Track F + G complete

**Decision:** Freeze for field testing at **`v0.5.0-advisory-beta`** (package **0.5.0**)
once this branch lands on `main`. That cut includes Track F **and** Track G
(small→larger temporal models, sequences, distributional CRPS).

Until the tag is cut, prefer `main` tip after the Track G merge.

---

## What is frozen (in scope for testing)

| Layer | Exercise |
|-------|----------|
| Offline ML | `make ml-e2e` |
| Temporal models | `axial_small` (default), optional `axial_large` / `transformer` / `transformer_dist` with `[torch]` |
| Multi-poll sequences | free-first re-observe appends `data_root/ml/market_sequences.jsonl` |
| Fixture sequences | `fixtures/sequences/synthetic_totals.json` |
| Distributional | `transformer_dist` → `total_probs` + CRPS in train metrics |
| Operator API | `/v1/ml/*` including axial train with `arch_preset` |
| Product law | authorities always false |

Default CI: **`[dev]` only** (torch tests skip).

---

## Field-test checklist

```bash
git checkout v0.5.0-advisory-beta   # after tag exists; else main post-G merge
python3 -m venv .venv && source .venv/bin/activate
pip install -e "packages/hollersports[dev]"

make smoke
make ml-e2e
make api && make web
make backfill-status

# Optional torch capacity (not required for freeze pass)
pip install -e "packages/hollersports[torch]"
make ml-axial-train
make ml-axial-train-transformer
```

**Pass:** smoke + ml-e2e green; authorities never true; annotate respects calibration ladder.

---

## Post-freeze research only

- Authenticated social firehoses  
- GPU-scale training on real minute streams  
- Any money rails (**never**)

See [TRACK_F_FUTURE_TRANSFORMERS.md](TRACK_F_FUTURE_TRANSFORMERS.md) for history of phases (G0–G4 now implemented at research scale).
