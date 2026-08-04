# Hermes — fixture backfill playbook

**Audience:** Hermes / agent workers that must grow paper-settlement sample for advice calibration.  
**Product law:** advisory only — **no real money**, **no book placement**, **no capital**.

---

## 60-second path (do this)

```bash
# From repo root: /home/scrimshawlife/Hollersports  (or clone root)
cd "$(git rev-parse --show-toplevel)"

# 1) See what needs backfilling (JSON + human lines)
python scripts/backfill_status.py
# or: make backfill-status

# 2) If needs_backfill is true, run the exact command printed by status
#    (or the default below)
make backfill
# equivalent:
# python scripts/backfill_fixtures.py \
#   --repeats 4 --paper-top-n 50 \
#   --data-root data/backfill \
#   --out docs/evidence/backfill_calibration.last.json

# 3) Confirm done
python scripts/backfill_status.py --assert-min-sample 20
# exit 0 → enough sample for RELIABLE floor *possibility*
# (RELIABLE also needs hit_rate / sim_roi floors — re-check status JSON)
```

**Stop when** `scripts/backfill_status.py` reports `needs_backfill: false` **or** you only needed a partial grow and the receipt is written.

---

## Where to look (discoverability)

| What | Path |
|------|------|
| **This playbook** | `docs/agents/HERMES_BACKFILL.md` |
| Agent index | `docs/agents/README.md` |
| Repo agent entry | `AGENTS.md` (root) |
| Status CLI | `scripts/backfill_status.py` · `make backfill-status` |
| Backfill CLI | `scripts/backfill_fixtures.py` · `make backfill` |
| Fixture days | `fixtures/day001/`, `fixtures/day002/` (+ any new `fixtures/day*/`) |
| Fixture inventory | `fixtures/MANIFEST.json` |
| Cumulative bank | `data/backfill/ledgers/settlements_history.jsonl` |
| Last receipt | `docs/evidence/backfill_calibration.last.json` |
| Calibration rules | `docs/TESTING_AND_CALIBRATION.md` |
| Human ops notes | `docs/BACKFILL_AND_NIGHTLY.md` |

**Do not invent fixtures.** Only run directories listed under `fixtures/` that contain `meta.json` + `odds_records.json` + `results.json`.

---

## What “needs backfilling” means

Backfill = re-run offline fixture operator days and **append** settled paper outcomes into the shared calibration bank so sample size grows.

| Signal | Source | Action |
|--------|--------|--------|
| `needs_backfill: true` | `backfill_status.py` | Run `make backfill` (or suggested cmd) |
| `current_sample` &lt; `target_sample` | status JSON | Default target **20** (RELIABLE sample floor) |
| Missing bank file | no `settlements_history.jsonl` | Run backfill once |
| New fixture day added | `fixtures/day00N` not in last receipt | Re-run with `--fixtures day001 day002 day00N` |
| Stale receipt | receipt older / lower sample than bank | Optional re-run; bank is source of truth |

**Default targets (advice calibration only):**

| Metric | Target | Notes |
|--------|--------|--------|
| `sample_size` | ≥ 20 | `DEFAULT_MIN_SAMPLE_RELIABLE` |
| `status` | prefer `WATCH` or `RELIABLE` | `EMPTY`/`UNRELIABLE` → keep backfilling |
| `model_edge_allowed` | may stay `false` | Needs RELIABLE + allow flag; not required for backfill success |

Backfill success = **bank grew + receipt written + no capital authority**. Reaching `RELIABLE` is ideal but depends on hit_rate/sim_roi, not only n.

---

## Preconditions

```bash
# Python env with package installed
test -x .venv/bin/python || python3 -m venv .venv
. .venv/bin/activate   # or use .venv/bin/python explicitly
pip install -e "packages/hollersports[dev]" -q
```

- Cwd = **repo root** (so `fixtures/` and `schemas/` resolve).
- Network **not** required for fixture backfill.
- Do **not** set live book / payment env vars; none are used.

---

## Execute (detailed)

### A. Status only (always safe)

```bash
python scripts/backfill_status.py
python scripts/backfill_status.py --json   # machine-only
```

Example fields:

```json
{
  "needs_backfill": true,
  "fixtures_available": ["day001", "day002"],
  "current_sample": 0,
  "target_sample": 20,
  "data_root": "data/backfill",
  "suggested_command": "python scripts/backfill_fixtures.py ...",
  "product_law": { "capital_authority": false, "real_money": false }
}
```

### B. Full default backfill

```bash
make backfill
```

Defaults inside `scripts/backfill_fixtures.py`:

- fixtures: all in `DEFAULT_FIXTURES` (`day001`, `day002`) — or pass `--fixtures`
- `--repeats 4` — each fixture run 4 times
- `--paper-top-n 50` — paper many candidates per run
- `--data-root data/backfill`
- `--out docs/evidence/backfill_calibration.last.json`

### C. Targeted / incremental

```bash
# Only new fixture
python scripts/backfill_fixtures.py --fixtures day002 --repeats 6 \
  --data-root data/backfill --out docs/evidence/backfill_calibration.last.json

# More sample aggressively
python scripts/backfill_fixtures.py --repeats 8 --paper-top-n 100 \
  --data-root data/backfill --out docs/evidence/backfill_calibration.last.json
```

### D. Verify

```bash
python scripts/backfill_status.py --assert-min-sample 20
# exit 0 = sample floor met

# Optional: read receipt
python -c "import json; print(json.load(open('docs/evidence/backfill_calibration.last.json'))['calibration'])"
```

---

## Outputs Hermes must leave behind

| Artifact | Required |
|----------|----------|
| `data/backfill/ledgers/settlements_history.jsonl` | Yes (gitignored under `data/` — local bank) |
| `docs/evidence/backfill_calibration.last.json` | Yes if using default `--out` (commit only if policy allows evidence receipts) |
| stdout JSON from status after run | Recommended in agent summary |

**Report to human (short):**

1. `current_sample` before → after  
2. `calibration.status`  
3. `needs_backfill` now true/false  
4. Command run  

---

## Done checklist

- [ ] Ran `scripts/backfill_status.py` first  
- [ ] Ran backfill if `needs_backfill`  
- [ ] Re-ran status; sample ≥ target **or** documented why not (e.g. only one fixture exists)  
- [ ] No `capital_authority` / `execution_authority` true anywhere in receipt  
- [ ] Did **not** call free-first live network unless human asked  
- [ ] Did **not** touch books, wallets, or live execution  

---

## Failures / recovery

| Failure | Fix |
|---------|-----|
| `fixture missing` | List `fixtures/`; only use dirs with full day pack |
| `ModuleNotFoundError: hollersports` | `pip install -e "packages/hollersports[dev]"` |
| Wrong cwd | `cd` to repo root |
| Sample still low after one run | Increase `--repeats` (e.g. 8–12) and re-run; bank **appends** |
| Want clean slate | Delete `data/backfill/` (local only) then re-run |

---

## Out of scope for Hermes backfill

- Vercel deploy, PyPI, multi-tenant auth  
- Real sportsbook / odds placement  
- Changing calibration **thresholds** without human approval  
- Live free-first (`make free-first`) unless explicitly requested  

---

## Related code (if debugging)

| Module | Role |
|--------|------|
| `scripts/backfill_fixtures.py` | Multi-day operator loop + bank append |
| `scripts/backfill_status.py` | Inventory + needs_backfill |
| `hollersports.paper.settlement_history` | JSONL bank |
| `hollersports.runes.calibration_evaluator` | EMPTY→…→RELIABLE ladder |
| `hollersports.pipelines.operator_day` | Single fixture closed loop |
