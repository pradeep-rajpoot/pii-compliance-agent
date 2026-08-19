"""pii-detection-agent: parses the uploaded file, sends the extracted text to
Claude (via Amazon Bedrock) in chunks using a forced tool-use call, validates
the results, and stores the final Detection[] on the job record.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from anthropic import APIError, AsyncAnthropicBedrock

from src.agents.detection_validation import validate_and_merge
from src.config import get_settings
from src.exceptions import AppError
from src.jobs.store import JobStore
from src.logging_utils import log_job_event
from src.models.block import TextBlock
from src.models.detection import RawDetection
from src.models.enums import JobStatus
from src.models.errors import ErrorCode
from src.parsers import parse_file
from src.pii_categories import PII_CATEGORIES

logger = logging.getLogger(__name__)

TOOL_NAME = "report_pii_detections"

SYSTEM_PROMPT = (
    "You are a PII (personally identifiable information) detection engine. "
    "You will be given a list of text blocks, each with a unique block_id, "
    "extracted from a document. Find every span of text that contains PII. "
    "For each finding, report the exact block_id it came from, the exact "
    "substring matched (matched_text must be an exact, verbatim substring of "
    "that block's text -- copy it character-for-character, do not "
    "paraphrase or normalize it), the character start_offset and end_offset "
    "of that substring within the block's text (0-indexed, end exclusive), "
    "a pii_type from the allowed categories, and a confidence score between "
    "0 and 1. Only report genuine PII; do not invent findings. Call the "
    f"{TOOL_NAME} tool exactly once with all findings across all the blocks "
    "given to you in this message."
)


def _tool_schema() -> dict:
    # The enum is generated from PII_CATEGORIES at call time -- this is what
    # lets new categories be added in src/pii_categories.py without touching
    # this prompt/schema or any validation code.
    return {
        "name": TOOL_NAME,
        "description": "Report all detected PII spans found in the given text blocks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "detections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "block_id": {"type": "string"},
                            "matched_text": {"type": "string"},
                            "pii_type": {
                                "type": "string",
                                "enum": list(PII_CATEGORIES),
                            },
                            "start_offset": {"type": "integer"},
                            "end_offset": {"type": "integer"},
                            "confidence": {"type": "number"},
                        },
                        "required": [
                            "block_id",
                            "matched_text",
                            "pii_type",
                            "start_offset",
                            "end_offset",
                            "confidence",
                        ],
                    },
                }
            },
            "required": ["detections"],
        },
    }


def build_client() -> AsyncAnthropicBedrock:
    """Construction point for the Bedrock client -- monkeypatched in tests
    so no automated test ever hits real Bedrock, even though real credentials
    are available in this environment."""

    settings = get_settings()
    return AsyncAnthropicBedrock(aws_region=settings.bedrock_region)


def render_chunk(chunk: list[TextBlock]) -> str:
    parts = []
    for block in chunk:
        parts.append(f"<block id={block.id!r}>\n{block.text}\n</block>")
    return "\n\n".join(parts)


def build_chunks(
    blocks: list[TextBlock], char_limit: int, max_blocks: int
) -> list[list[TextBlock]]:
    """Greedy bin-pack blocks, in original order, respecting both a total
    character budget and a max-blocks-per-chunk cap. An oversized single
    block (bigger than char_limit on its own) becomes its own chunk rather
    than being split mid-block."""

    chunks: list[list[TextBlock]] = []
    current: list[TextBlock] = []
    current_chars = 0

    for block in blocks:
        block_len = len(block.text)
        would_exceed_chars = current and (current_chars + block_len > char_limit)
        would_exceed_count = current and (len(current) + 1 > max_blocks)
        if would_exceed_chars or would_exceed_count:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(block)
        current_chars += block_len

    if current:
        chunks.append(current)

    return chunks


async def _call_bedrock_with_retry(
    client: AsyncAnthropicBedrock,
    model_id: str,
    chunk_text: str,
    timeout_seconds: float,
    job_id: str,
    chunk_index: int,
) -> list[dict]:
    last_exc: Exception | None = None
    for attempt in range(2):  # one initial try + exactly one retry
        try:
            message = await asyncio.wait_for(
                client.messages.create(
                    model=model_id,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=[_tool_schema()],
                    tool_choice={"type": "tool", "name": TOOL_NAME},
                    messages=[{"role": "user", "content": chunk_text}],
                ),
                timeout=timeout_seconds,
            )
            for block in message.content:
                if getattr(block, "type", None) == "tool_use":
                    return block.input.get("detections", [])
            return []
        except (TimeoutError, APIError) as exc:
            last_exc = exc
            log_job_event(
                logger,
                job_id,
                "detection_llm_call",
                level=logging.WARNING,
                chunk_index=chunk_index,
                attempt=attempt,
                error_type=type(exc).__name__,
            )
    assert last_exc is not None
    raise last_exc


async def run_detection(job_id: str, store: JobStore) -> None:
    settings = get_settings()
    await store.update(job_id, status=JobStatus.DETECTING)
    log_job_event(logger, job_id, "detection_start")

    try:
        record = await store.get(job_id)

        try:
            parsed = parse_file(record.file_type, Path(record.original_path))
        except Exception as exc:  # noqa: BLE001
            log_job_event(
                logger,
                job_id,
                "detection_parse_error",
                level=logging.ERROR,
                error_type=type(exc).__name__,
            )
            raise AppError(
                ErrorCode.PARSE_ERROR, f"Failed to parse file: {exc}"
            ) from exc

        blocks = parsed.blocks
        # Strip non-JSON-safe entries (e.g. an in-memory openpyxl Workbook)
        # before persisting parse metadata on the job record.
        parse_meta = {k: v for k, v in parsed.meta.items() if k != "workbook"}
        await store.update(job_id, blocks=blocks, parse_meta=parse_meta)

        chunks = build_chunks(
            blocks,
            settings.detection_chunk_char_limit,
            settings.detection_max_blocks_per_chunk,
        )

        if len(chunks) > settings.detection_max_chunks_per_job:
            raise AppError(
                ErrorCode.LLM_ERROR,
                f"Document requires {len(chunks)} LLM calls, exceeding the "
                f"per-job cap of {settings.detection_max_chunks_per_job}.",
            )

        raw_detections: list[RawDetection] = []
        if chunks:
            client = build_client()
            for i, chunk in enumerate(chunks):
                try:
                    items = await _call_bedrock_with_retry(
                        client,
                        settings.bedrock_model_id,
                        render_chunk(chunk),
                        settings.llm_timeout_seconds,
                        job_id,
                        i,
                    )
                except (TimeoutError, APIError) as exc:
                    log_job_event(
                        logger,
                        job_id,
                        "detection_llm_failed",
                        level=logging.ERROR,
                        chunk_index=i,
                        error_type=type(exc).__name__,
                    )
                    raise AppError(
                        ErrorCode.LLM_ERROR,
                        f"LLM call failed after retry: {exc}",
                    ) from exc

                for item in items:
                    try:
                        raw_detections.append(RawDetection(**item))
                    except Exception as exc:  # noqa: BLE001
                        log_job_event(
                            logger,
                            job_id,
                            "detection_raw_parse_error",
                            level=logging.WARNING,
                            error_type=type(exc).__name__,
                        )

        detections = validate_and_merge(raw_detections, blocks, job_id)

        await store.update(
            job_id, status=JobStatus.DETECTED, detections=detections
        )
        log_job_event(
            logger,
            job_id,
            "detection_complete",
            detection_count=len(detections),
        )

    except AppError as exc:
        await store.update(
            job_id,
            status=JobStatus.FAILED,
            error={"code": exc.code.value, "message": exc.message},
        )
        log_job_event(
            logger,
            job_id,
            "detection_failed",
            level=logging.ERROR,
            error_code=exc.code.value,
        )
    except Exception as exc:  # noqa: BLE001
        await store.update(
            job_id,
            status=JobStatus.FAILED,
            error={"code": ErrorCode.LLM_ERROR.value, "message": str(exc)},
        )
        log_job_event(
            logger,
            job_id,
            "detection_failed",
            level=logging.ERROR,
            error_code=ErrorCode.LLM_ERROR.value,
            error_type=type(exc).__name__,
        )
