# Track G — Temporal models & sequences (implemented at research scale)

**Status:** Implemented on the path to freeze **`v0.5.0-advisory-beta`**.  
This is still **advisory research** — not a claim of production betting quality.

---

## Delivered phases

### G0 — Sequence plumbing

- Multi-poll append: `sources/sequence_store.py` → `data_root/ml/market_sequences.jsonl`  
  (wired from free-first odds enrichment when `data_root` set)
- Fixture sequences: `fixtures/sequences/synthetic_totals.json`
- Train can merge day windows + store + fixture sequences

### G1 — Capacity behind same interface

| Preset | Arch | d_model | layers | heads |
|--------|------|---------|--------|-------|
| `axial_small` | axial | 32 | 2 | 4 |
| `axial_large` | axial | 64 | 4 | 8 |
| `transformer` | TransformerEncoder | 64 | 4 | 8 |
| `transformer_dist` | TransformerEncoder + total bins | 64 | 4 | 8 |

CLI: `make ml-axial-train-large` / `make ml-axial-train-transformer`  
API: `POST /v1/ml/axial/train` with `arch_preset`

### G2 — Distributional head

- `transformer_dist`: softmax over total bins 0–10+  
- CRPS in train metrics (`train_crps`)  
- Score packet may include `total_probs` + `expected_total`  
- Still ADVISORY_ONLY; does not place bets

### G3 — Text

- RSS inject + opt-in fetch remains the live text path (no Twitter in freeze)

### G4 — Ops

- Axial/transformer train writes model cards under `out_dir/model_cards/`  
- Retrain-apply still requires `confirm=true`

---

## Packet contracts (stable)

- `HollerAxialTorch.v1` (probability ± optional total_probs)  
- `HollerFixtureSequences.v1`  
- Ensemble logistic path unchanged for CI default  

---

## What larger *production* systems would still need

- Real minute-level event streams (not only synthetic + multi-poll)  
- Large settled banks for RELIABLE promotion  
- GPU ops budget  

Those are **post-field-test** investments, not blockers for the v0.5 freeze.
