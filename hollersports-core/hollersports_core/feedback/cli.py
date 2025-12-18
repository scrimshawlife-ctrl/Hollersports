from __future__ import annotations
import argparse
from pathlib import Path

from ..util.io import read_json, write_json, append_line
from ..util.time import now_utc_iso
from ..util.hashing import stable_json_dumps, sha256_hex
from ..util.deterministic import seed_everything

from ..schema.expected import ExpectedOutcome
from ..schema.result import GameResult
from ..schema.state import ModelState
from ..schema.ledger import LedgerEntry
from ..schema.types import Provenance
from ..schema.feedback import FeedbackRecord

from .calibrator import compute_metrics
from .updater import update_state_with_feedback


def _load_prev_hash(ledger_path: Path) -> str:
    if not ledger_path.exists():
        return "GENESIS"
    # last line's this_ledger_hash
    last = ledger_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    import json
    obj = json.loads(last)
    return obj["provenance"]["this_ledger_hash"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--ledger_dir", required=True)
    ap.add_argument("--run_id", required=False, default=None)
    args = ap.parse_args()

    exp = ExpectedOutcome.model_validate(read_json(args.expected))
    res = GameResult.model_validate(read_json(args.result))
    state = ModelState.model_validate(read_json(args.state))

    # Determinism: seed from expected.seed (ties feedback to original sim seed)
    seed_everything(exp.seed)

    metrics = compute_metrics(exp, res)
    new_state, priors = update_state_with_feedback(state, exp, metrics)

    record = FeedbackRecord(
        expected=exp,
        result=res,
        metrics=metrics,
        new_fatigue_weight=priors.fatigue_weight,
        new_tempo_bias=priors.tempo_bias,
        new_streak_compression=priors.streak_compression,
    )

    # Provenance + hash chain
    ledger_path = Path(args.ledger_dir) / f"{exp.sport.lower()}_feedback.jsonl"
    prev_hash = _load_prev_hash(ledger_path)

    created = now_utc_iso()
    run_id = args.run_id or f"{exp.sport}:{exp.game_id}:{created}"

    input_payload = {
        "expected": exp.model_dump(),
        "result": res.model_dump(),
        "state_before": state.model_dump(),
        "prev_hash": prev_hash,
    }
    input_hash = sha256_hex(stable_json_dumps(input_payload))

    # this_ledger_hash is computed from the entry without this_ledger_hash, then inserted
    proto = {
        "provenance": {
            "run_id": run_id,
            "created_utc": created,
            "input_hash": input_hash,
            "prev_ledger_hash": prev_hash,
            "this_ledger_hash": "PENDING",
        },
        "record": record.model_dump(),
    }
    this_hash = sha256_hex(stable_json_dumps({**proto, "provenance": {**proto["provenance"], "this_ledger_hash": ""}}))

    prov = Provenance(
        run_id=run_id,
        created_utc=created,
        input_hash=input_hash,
        prev_ledger_hash=prev_hash,
        this_ledger_hash=this_hash,
    )
    entry = LedgerEntry(provenance=prov, record=record)

    append_line(ledger_path, stable_json_dumps(entry.model_dump()))

    # Persist updated state deterministically
    write_json(args.state, new_state.model_dump())


if __name__ == "__main__":
    main()
