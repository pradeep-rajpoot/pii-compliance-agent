from __future__ import annotations

from pydantic import BaseModel


class RawDetection(BaseModel):
    """Untrusted, as-returned-by-the-LLM shape. Must be validated
    (src/agents/detection_validation.py) before it is trusted for anything
    (rendering to the frontend, or later, masking the original file)."""

    block_id: str
    matched_text: str
    pii_type: str
    start_offset: int
    end_offset: int
    confidence: float


class Detection(BaseModel):
    """Validated, API-facing shape. `matched_text` from RawDetection is
    renamed to `value` here once it has been confirmed to actually match
    (or been re-anchored against) the source block text."""

    id: str
    block_id: str
    pii_type: str
    value: str
    start_offset: int
    end_offset: int
    confidence: float
