from __future__ import annotations
from pydantic import BaseModel
from .types import Provenance
from .feedback import FeedbackRecord


class LedgerEntry(BaseModel):
    provenance: Provenance
    record: FeedbackRecord
