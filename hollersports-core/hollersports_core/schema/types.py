from __future__ import annotations
from pydantic import BaseModel, Field


class Provenance(BaseModel):
    run_id: str = Field(..., description="Unique run identifier (stable across pipeline)")
    created_utc: str = Field(..., description="UTC ISO timestamp")
    input_hash: str = Field(..., description="sha256 of stable JSON of inputs used")
    prev_ledger_hash: str = Field(..., description="Hash of previous ledger entry (hash chain), or 'GENESIS'")
    this_ledger_hash: str = Field(..., description="Hash of this ledger entry payload")
