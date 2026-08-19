"""pii-correction-agent: deterministic, NOT LLM-driven. Consumes the already
-validated Detection[] from the job record and the original file, and
produces a masked copy in the original format (PDF is the one exception --
see the module-level docstring on `_correct_pdf`).

The router is responsible for checking the job is in "detected" state and
flipping it to "correcting" *before* scheduling this coroutine, to avoid a
race between two concurrent POST /correct calls. This function assumes that
has already happened.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape as xml_escape

from docx import Document
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate
from reportlab.lib.styles import getSampleStyleSheet

from src.agents.masking import apply_masks
from src.exceptions import AppError
from src.jobs.store import JobRecord, JobStore
from src.logging_utils import log_job_event
from src.models.detection import Detection
from src.models.enums import FileType, JobStatus
from src.models.errors import ErrorCode
from src.models.locator import CsvLocator, JsonLocator, XlsxLocator
from src.parsers import csv as csv_parser
from src.parsers import parse_file
from src.parsers.docx import compute_run_offsets

logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    FileType.PDF: "application/pdf",
    FileType.XLSX: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    FileType.XLS: "application/vnd.ms-excel",
    FileType.CSV: "text/csv",
    FileType.DOCX: (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    FileType.JSON: "application/json",
}

EXTENSIONS = {
    FileType.PDF: ".pdf",
    FileType.XLSX: ".xlsx",
    FileType.XLS: ".xls",
    FileType.CSV: ".csv",
    FileType.DOCX: ".docx",
    FileType.JSON: ".json",
}


def _group_by_block(detections: list[Detection]) -> dict[str, list[Detection]]:
    grouped: dict[str, list[Detection]] = {}
    for d in detections:
        grouped.setdefault(d.block_id, []).append(d)
    return grouped


def _corrected_dir(temp_dir: str) -> Path:
    out_dir = Path(temp_dir) / "corrected"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _correct_xlsx(record: JobRecord, by_block: dict[str, list[Detection]]) -> Path:
    parsed = parse_file(record.file_type, Path(record.original_path))
    workbook = parsed.meta.get("workbook")
    if workbook is None:
        raise AppError(
            ErrorCode.CORRECTION_ERROR,
            "Correcting legacy .xls files is not supported in v1 "
            "(no writer library for the legacy binary format); "
            "re-save as .xlsx and re-upload.",
        )

    for block in parsed.blocks:
        dets = by_block.get(block.id)
        if not dets:
            continue
        locator = block.locator
        assert isinstance(locator, XlsxLocator)
        masked = apply_masks(block.text, dets)
        workbook[locator.sheet][locator.cell] = masked

    out_path = _corrected_dir(record.temp_dir) / f"{uuid4().hex}.xlsx"
    workbook.save(str(out_path))
    return out_path


def _correct_csv(record: JobRecord, by_block: dict[str, list[Detection]]) -> Path:
    import csv as csv_stdlib

    dialect_kwargs = record.parse_meta.get("dialect")
    if not dialect_kwargs:
        # Shouldn't normally happen (detection always persists it), but fall
        # back to sniffing rather than crashing the job.
        sample = Path(record.original_path).read_text(
            encoding="utf-8-sig", errors="replace"
        )
        dialect_kwargs = csv_parser.sniff_dialect_kwargs(sample)

    with open(
        record.original_path, "r", encoding="utf-8-sig", newline="", errors="replace"
    ) as f:
        rows = list(csv_stdlib.reader(f, **dialect_kwargs))

    for block_id, dets in by_block.items():
        # block ids are "r{row}c{col}" (see parsers/csv.py)
        row_col = block_id[1:].split("c", 1)
        row_idx, col_idx = int(row_col[0]), int(row_col[1])
        if row_idx >= len(rows) or col_idx >= len(rows[row_idx]):
            log_job_event(
                logger,
                record.job_id,
                "correction_csv_skip",
                level=logging.WARNING,
                block_id=block_id,
                reason="out_of_range",
            )
            continue
        rows[row_idx][col_idx] = apply_masks(rows[row_idx][col_idx], dets)

    out_path = _corrected_dir(record.temp_dir) / f"{uuid4().hex}.csv"
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv_stdlib.writer(f, **dialect_kwargs)
        writer.writerows(rows)
    return out_path


def _correct_docx(record: JobRecord, by_block: dict[str, list[Detection]]) -> Path:
    document = Document(record.original_path)

    for i, paragraph in enumerate(document.paragraphs):
        block_id = f"p{i}"
        dets = by_block.get(block_id)
        if not dets:
            continue

        run_offsets = compute_run_offsets(paragraph)
        runs = paragraph.runs

        for det in sorted(dets, key=lambda d: d.start_offset):
            for run_index, run_start, run_end in run_offsets:
                overlap_start = max(run_start, det.start_offset)
                overlap_end = min(run_end, det.end_offset)
                if overlap_start >= overlap_end:
                    continue  # this run isn't touched by this detection
                run = runs[run_index]
                rel_start = overlap_start - run_start
                rel_end = overlap_end - run_start
                run.text = (
                    run.text[:rel_start]
                    + "X" * (rel_end - rel_start)
                    + run.text[rel_end:]
                )

    out_path = _corrected_dir(record.temp_dir) / f"{uuid4().hex}.docx"
    document.save(str(out_path))
    return out_path


def _correct_pdf(record: JobRecord, by_block: dict[str, list[Detection]]) -> Path:
    """PDFs aren't edited in place. v1 re-renders an entirely new PDF from
    the masked, extracted text using simple flowed text per page (no attempt
    at pixel-perfect layout preservation) -- a documented fidelity
    limitation, not a bug. See spec §7 / §13."""

    parsed = parse_file(record.file_type, Path(record.original_path))

    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]

    out_path = _corrected_dir(record.temp_dir) / f"{uuid4().hex}.pdf"
    doc = SimpleDocTemplate(str(out_path), pagesize=LETTER)

    story = []
    for idx, block in enumerate(parsed.blocks):
        dets = by_block.get(block.id)
        text = apply_masks(block.text, dets) if dets else block.text
        for line in text.splitlines() or [""]:
            story.append(Paragraph(xml_escape(line) or "&nbsp;", body_style))
        if idx < len(parsed.blocks) - 1:
            story.append(PageBreak())

    if not story:
        story = [Paragraph("", body_style)]

    doc.build(story)
    return out_path


def _set_at_path(data: object, path: list, value: str) -> None:
    node = data
    for segment in path[:-1]:
        node = node[segment]  # type: ignore[index]
    node[path[-1]] = value  # type: ignore[index]


def _correct_json(record: JobRecord, by_block: dict[str, list[Detection]]) -> Path:
    import json as json_stdlib

    data = json_stdlib.loads(
        Path(record.original_path).read_text(encoding="utf-8")
    )
    parsed = parse_file(record.file_type, Path(record.original_path))

    for block in parsed.blocks:
        dets = by_block.get(block.id)
        if not dets:
            continue
        locator = block.locator
        assert isinstance(locator, JsonLocator)
        masked = apply_masks(block.text, dets)
        # A masked leaf always becomes a JSON string, even if the original
        # value was a number/bool (e.g. an SSN stored as an int) -- same
        # type-fidelity tradeoff as xlsx formula-result cells.
        _set_at_path(data, locator.path, masked)

    out_path = _corrected_dir(record.temp_dir) / f"{uuid4().hex}.json"
    out_path.write_text(
        json_stdlib.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return out_path


_CORRECTORS = {
    FileType.XLSX: _correct_xlsx,
    FileType.XLS: _correct_xlsx,
    FileType.CSV: _correct_csv,
    FileType.DOCX: _correct_docx,
    FileType.PDF: _correct_pdf,
    FileType.JSON: _correct_json,
}


async def run_correction(job_id: str, store: JobStore) -> None:
    log_job_event(logger, job_id, "correction_start")
    try:
        record = await store.get(job_id)
        by_block = _group_by_block(record.detections)

        corrector = _CORRECTORS[record.file_type]
        out_path = corrector(record, by_block)

        original_stem = Path(record.original_filename).stem
        ext = EXTENSIONS[record.file_type] if record.file_type != FileType.XLS else ".xlsx"
        corrected_filename = f"{original_stem}-pii-safe{ext}"
        content_type = CONTENT_TYPES[record.file_type]

        await store.update(
            job_id,
            status=JobStatus.CORRECTED,
            corrected_file_path=str(out_path),
            corrected_filename=corrected_filename,
            content_type=content_type,
        )
        log_job_event(logger, job_id, "correction_complete")

    except AppError as exc:
        await store.update(
            job_id,
            status=JobStatus.FAILED,
            error={"code": exc.code.value, "message": exc.message},
        )
        log_job_event(
            logger,
            job_id,
            "correction_failed",
            level=logging.ERROR,
            error_code=exc.code.value,
        )
    except Exception as exc:  # noqa: BLE001
        await store.update(
            job_id,
            status=JobStatus.FAILED,
            error={"code": ErrorCode.CORRECTION_ERROR.value, "message": str(exc)},
        )
        log_job_event(
            logger,
            job_id,
            "correction_failed",
            level=logging.ERROR,
            error_code=ErrorCode.CORRECTION_ERROR.value,
            error_type=type(exc).__name__,
        )
