from __future__ import annotations

from src.models.detection import Detection


def mask(text: str, start: int, end: int) -> str:
    """Length-preserving mask: replace text[start:end] with 'X' * (end-start).

    For non-overlapping spans within the same block, the order in which
    multiple calls are applied doesn't matter -- each call only rewrites
    characters strictly inside its own [start, end) range and never changes
    the string's length, so indices computed against the *original* text
    remain valid against the *already-partially-masked* text too.
    """

    return text[:start] + "X" * (end - start) + text[end:]


def apply_masks(text: str, detections: list[Detection]) -> str:
    result = text
    for d in sorted(detections, key=lambda d: d.start_offset):
        result = mask(result, d.start_offset, d.end_offset)
    return result
