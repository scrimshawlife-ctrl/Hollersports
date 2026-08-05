# Future work — production-scale transformers (post-freeze)

**Status:** Deferred until [TRACK_F_FREEZE_AND_FIELD_TEST.md](TRACK_F_FREEZE_AND_FIELD_TEST.md) field testing of **v0.4.0** is complete enough to unfreeze.

This is **not** a commitment to ship large models. It records *when* and *how* they would help, so agents do not expand model scope during the freeze window.

---

## Current (frozen) stack

| Component | Role in freeze |
|-----------|----------------|
| L2 logistic (+ optional sklearn HGB) | Default trainable baseline; CI-safe |
| Temperature ensemble | Small-n-safe calibration |
| EV → `model_probability` | Feeds gated `MODEL_PROBABILITY_EDGE` |
| Axial **stub** | Always available dual-axis smooth |
| Axial **torch** (small) | Optional `[torch]`; research, not advice floor |
| RSS + lexicon | Text features without social firehose |

Packet contracts to keep stable for any future swap-in:

- `HollerAxialTorch.v1` / `HollerAxialStub.v1`
- `HollerMlAnnotatePacket.v1` / ensemble meta JSON
- Calibration ladder + `confirm=true` retrain-apply

---

## What larger transformers would unlock

1. **In-play / tick sequences** — long-range temporal structure (threat building, odds path) once free-first stores multi-poll or minute-level tensors.  
2. **Distributional forecasts** — full score distributions (CRPS), not only moneyline p, for totals/spreads EV.  
3. **Multi-source fusion** — odds path + structured stats + short text embeddings when sequences are long enough that hand features plateau.  
4. **Same product law** — still advisory; still fail-closed; still calibration-gated. Bigger nets do **not** enable money rails.

See research notes: [arxiv_research_summary.md](arxiv_research_summary.md).

---

## What they will not fix

- Empty or small settlement banks  
- Missing odds / provenance (fail closed stays)  
- Overfit on three fixture days  
- Operator UX or Hermes backfill discipline  

---

## Suggested post-unfreeze phases (Track G)

### G0 — Data plumbing (do first)

- [ ] Persist free-first multi-poll odds snapshots as **ordered sequences** per `event_id` (not only latest).  
- [ ] Fixture format for minute/event streams (or synthetic high-T sequences for unit tests).  
- [ ] Evidence: N days of free-first closed day + bank ≥ RELIABLE-capable sample.

### G1 — Capacity behind existing interface

- [ ] Larger axial / Transformer **behind** `score_sequence_torch` / same meta JSON schema.  
- [ ] Train on real sequences; report Brier/CRPS on held-out days in model card.  
- [ ] Keep logistic as CI default; torch remains optional extra.

### G2 — Distributional head (optional)

- [ ] Goal-count or score-bin head; CRPS in retrain-check.  
- [ ] Map distribution → market EV for totals/spreads (still ADVISORY_ONLY).

### G3 — Text/social (optional)

- [ ] Authenticated social or richer news only after RSS field-test lessons.  
- [ ] Never invent text; inject path for CI always required.

### G4 — Ops

- [ ] Hermes: proposal → human confirm → retrain-apply remains the only apply path.  
- [ ] Model card + continuum tip pin when a torch model is promoted for demos (still not money).

---

## Agent rules during freeze

1. **Do not** start G1–G4 unless the user unfreezes or cites this doc to proceed.  
2. Prefer fixing field-test bugs in the **small stack** (features, annotate, gates, Workbench).  
3. Prefer growing **backfill / free-first closed day** sample over new architectures.  
4. Any new model must remain **optional**, fail closed without weights, and preserve authorities false.

---

## Related

| Doc | Role |
|-----|------|
| [TRACK_F_FREEZE_AND_FIELD_TEST.md](TRACK_F_FREEZE_AND_FIELD_TEST.md) | Freeze decision + test checklist |
| [agents/HERMES_ML.md](agents/HERMES_ML.md) | How to run frozen ML path |
| [superpowers/specs/2026-08-05-hollersports-ml-pipeline-design.md](superpowers/specs/2026-08-05-hollersports-ml-pipeline-design.md) | Original Track F design |
