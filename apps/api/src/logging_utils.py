"""Structured logging helpers.

Every log call that touches job processing should go through
`log_job_event` instead of ad-hoc f-strings, specifically so that no PII
value / matched_text can ever land in a log line by accident: callers pass
structured keyword fields (counts, types, offsets, job/block ids) and this
module is the one place that decides what's safe to log.

NEVER pass a `value`, `matched_text`, or raw extracted `text` kwarg here.
"""

from __future__ import annotations

import logging
from typing import Any

_FORBIDDEN_KEYS = {"value", "matched_text", "text", "content"}


def log_job_event(
    logger: logging.Logger,
    job_id: str,
    stage: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    bad = _FORBIDDEN_KEYS & fields.keys()
    if bad:
        # Fail loudly in dev/tests rather than silently leak PII into logs.
        raise ValueError(
            f"log_job_event received forbidden field(s) that may contain PII: {bad}"
        )

    parts = " ".join(f"{k}={v!r}" for k, v in fields.items())
    logger.log(level, "job_id=%s stage=%s %s", job_id, stage, parts)
