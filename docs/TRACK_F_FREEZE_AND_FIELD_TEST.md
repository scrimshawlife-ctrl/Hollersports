# Release freeze — test after Track F + G complete

**Decision:** Freeze for field testing at **`v0.5.0-advisory-beta`** (package **0.5.0**).  
That cut includes Track F **and** Track G (sequences, larger temporal presets, CRPS).

**Tag exists.** Receipt after local verify: `docs/evidence/FIELD_TEST_RECEIPT_v0.5.0.json`  
(run `make field-test`).

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
git checkout v0.5.0-advisory-beta
python3 -m venv .venv && source .venv/bin/activate
# Makefile prefers python3 + PYTHONPATH=packages/hollersports
make field-test    # install + smoke + ml-e2e + FIELD_TEST_RECEIPT_v0.5.0.json

make api && make web
make backfill-status   # grow sample toward RELIABLE (field work, not freeze blocker)

# Optional torch capacity (not required for freeze pass)
pip install -e "packages/hollersports[torch]"
make ml-axial-train
make ml-axial-train-transformer
```

**Pass:** `make field-test` → verdict `FIELD_TEST_READY`; authorities false; ml-e2e candidates ≥ 1.

---

## Post-freeze research only

- Authenticated social firehoses  
- GPU-scale training on real minute streams  
- Any money rails (**never**)

See [TRACK_F_FUTURE_TRANSFORMERS.md](TRACK_F_FUTURE_TRANSFORMERS.md) for history of phases (G0–G4 now implemented at research scale).
