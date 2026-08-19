"""Validates untrusted RawDetection objects returned by the LLM against the
actual block text, re-anchors offset drift, drops what can't be resolved,
and merges overlapping same-type spans.

Hard requirement: nothing in this module may log `matched_text` / `value`.
Only job_id, block_id, and pii_type are safe to log (see src/logging_utils.py
which enforces this at the call site).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from src.logging_utils import log_job_event
from src.models.block import TextBlock
from src.models.detection import Detection, RawDetection
from src.pii_categories import PII_CATEGORIES

logger = logging.getLogger(__name__)


@dataclass
class _Span:
    pii_type: str
    start: int
    end: int
    confidence: float


def _validate_one(
    raw: RawDetection, block_text: str, job_id: str
) -> _Span | None:
    if raw.pii_type not in PII_CATEGORIES:
        log_job_event(
            logger,
            job_id,
            "detection_validation",
            level=logging.WARNING,
            block_id=raw.block_id,
            pii_type=raw.pii_type,
            reason="unknown_pii_type",
        )
        return None

    text_len = len(block_text)
    start, end = raw.start_offset, raw.end_offset

    # Out-of-bounds offsets are dropped outright -- no fallback attempt --
    # since they indicate the LLM's positional claim is unusable, distinct
    # from a same-length-range-but-wrong-content offset drift.
    if not (0 <= start < end <= text_len):
        log_job_event(
            logger,
            job_id,
            "detection_validation",
            level=logging.WARNING,
            block_id=raw.block_id,
            pii_type=raw.pii_type,
            reason="out_of_bounds_offset",
        )
        return None

    # Exact match: the LLM's claimed offsets line up with its claimed text.
    if block_text[start:end] == raw.matched_text:
        return _Span(raw.pii_type, start, end, raw.confidence)

    # Fallback: search for the matched text elsewhere in the block and
    # re-anchor to the occurrence closest to the claimed start offset.
    if raw.matched_text:
        candidates = list(re.finditer(re.escape(raw.matched_text), block_text))
        if candidates:
            best = min(candidates, key=lambda m: abs(m.start() - start))
            return _Span(raw.pii_type, best.start(), best.end(), raw.confidence)

    log_job_event(
        logger,
        job_id,
        "detection_validation",
        level=logging.WARNING,
        block_id=raw.block_id,
        pii_type=raw.pii_type,
        reason="unresolvable_offset",
    )
    return None


def _merge_spans(spans: list[_Span], block_text: str) -> list[_Span]:
    """Merge overlapping same-type spans within a single block."""

    by_type: dict[str, list[_Span]] = {}
    for span in spans:
        by_type.setdefault(span.pii_type, []).append(span)

    merged: list[_Span] = []
    for pii_type, group in by_type.items():
        group.sort(key=lambda s: s.start)
        current = group[0]
        for nxt in group[1:]:
            if nxt.start <= current.end:  # overlap (or touching)
                current = _Span(
                    pii_type,
                    min(current.start, nxt.start),
                    max(current.end, nxt.end),
                    max(current.confidence, nxt.confidence),
                )
            else:
                merged.append(current)
                current = nxt
        merged.append(current)

    merged.sort(key=lambda s: s.start)
    return merged


def validate_and_merge(
    raw_detections: list[RawDetection],
    blocks: list[TextBlock],
    job_id: str,
) -> list[Detection]:
    blocks_by_id = {b.id: b for b in blocks}

    spans_by_block: dict[str, list[_Span]] = {}
    for raw in raw_detections:
        block = blocks_by_id.get(raw.block_id)
        if block is None:
            log_job_event(
                logger,
                job_id,
                "detection_validation",
                level=logging.WARNING,
                block_id=raw.block_id,
                pii_type=raw.pii_type,
                reason="unknown_block_id",
            )
            continue
        span = _validate_one(raw, block.text, job_id)
        if span is not None:
            spans_by_block.setdefault(raw.block_id, []).append(span)

    detections: list[Detection] = []
    seq = 1
    # Iterate blocks in their original document order so detection ids are
    # stable and read top-to-bottom.
    for block in blocks:
        spans = spans_by_block.get(block.id)
        if not spans:
            continue
        for span in _merge_spans(spans, block.text):
            detections.append(
                Detection(
                    id=f"d{seq}",
                    block_id=block.id,
                    pii_type=span.pii_type,
                    value=block.text[span.start : span.end],
                    start_offset=span.start,
                    end_offset=span.end,
                    confidence=span.confidence,
                )
            )
            seq += 1

    return detections
