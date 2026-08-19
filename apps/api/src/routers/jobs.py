from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from src.agents.correction_agent import run_correction
from src.agents.detection_agent import run_detection
from src.config import get_settings
from src.exceptions import AppError
from src.jobs.store import JobRecord, JobStore, get_job_store
from src.logging_utils import log_job_event
from src.models.enums import FileType, JobStatus
from src.models.errors import ErrorCode, ErrorDetail
from src.models.job import JobResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_EXT_TO_FILE_TYPE = {
    ".pdf": FileType.PDF,
    ".xlsx": FileType.XLSX,
    ".xls": FileType.XLS,
    ".csv": FileType.CSV,
    ".docx": FileType.DOCX,
    ".json": FileType.JSON,
}


def _job_to_response(record: JobRecord) -> JobResponse:
    error = None
    if record.error:
        error = ErrorDetail(
            code=record.error["code"], message=record.error["message"]
        )
    return JobResponse(
        job_id=record.job_id,
        status=record.status,
        file_type=record.file_type,
        blocks=record.blocks,
        detections=record.detections,
        error=error,
    )


async def cleanup_job(store: JobStore, job_id: str) -> None:
    """Starlette one-shot BackgroundTask attached to the download
    FileResponse: deletes the job's temp dir + store entry right after a
    successful download, independent of the periodic TTL sweep."""

    try:
        record = await store.get(job_id)
    except AppError:
        return
    shutil.rmtree(record.temp_dir, ignore_errors=True)
    await store.delete(job_id)


@router.post("/detect", status_code=202)
async def detect(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    store: JobStore = Depends(get_job_store),
) -> dict:
    settings = get_settings()

    original_filename = file.filename or "upload"
    ext = Path(original_filename).suffix.lower()
    file_type = _EXT_TO_FILE_TYPE.get(ext)
    if file_type is None:
        raise AppError(
            ErrorCode.UNSUPPORTED_FILE_TYPE,
            f"Unsupported file extension: {ext or '(none)'}",
            http_status=415,
        )

    job_id = uuid4().hex
    temp_dir = tempfile.mkdtemp(prefix=f"pii-job-{job_id}-")
    os.chmod(temp_dir, 0o700)
    original_path = Path(temp_dir) / f"original{ext}"

    max_bytes = settings.max_upload_bytes
    total = 0
    try:
        with open(original_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppError(
                        ErrorCode.FILE_TOO_LARGE,
                        (
                            "File exceeds the maximum upload size of "
                            f"{max_bytes} bytes"
                        ),
                        http_status=413,
                    )
                out.write(chunk)
    except AppError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    finally:
        await file.close()

    await store.create(
        job_id=job_id,
        status=JobStatus.QUEUED,
        file_type=file_type,
        original_path=str(original_path),
        original_filename=original_filename,
        temp_dir=temp_dir,
    )

    background_tasks.add_task(run_detection, job_id, store)

    log_job_event(
        logger, job_id, "job_created", file_type=file_type.value, size_bytes=total
    )

    return {"job_id": job_id, "status": JobStatus.QUEUED.value}


@router.get("/{job_id}")
async def get_job(
    job_id: str, store: JobStore = Depends(get_job_store)
) -> JobResponse:
    record = await store.get(job_id)
    return _job_to_response(record)


@router.post("/{job_id}/correct", status_code=202)
async def correct(
    job_id: str,
    background_tasks: BackgroundTasks,
    store: JobStore = Depends(get_job_store),
) -> dict:
    record = await store.get(job_id)
    if record.status != JobStatus.DETECTED:
        raise AppError(
            ErrorCode.INVALID_JOB_STATE,
            (
                "Job must be in 'detected' state to correct, is "
                f"'{record.status.value}'"
            ),
            http_status=409,
        )
    # Flip state synchronously, before returning, so two concurrent
    # POST /correct calls can't both pass the check above and both schedule
    # a correction run.
    await store.update(job_id, status=JobStatus.CORRECTING)
    background_tasks.add_task(run_correction, job_id, store)
    return {"job_id": job_id, "status": JobStatus.CORRECTING.value}


@router.get("/{job_id}/download")
async def download(job_id: str, store: JobStore = Depends(get_job_store)):
    record = await store.get(job_id)
    if record.status != JobStatus.CORRECTED or not record.corrected_file_path:
        raise AppError(
            ErrorCode.FILE_NOT_READY,
            f"Job is not ready for download (status='{record.status.value}')",
            http_status=404,
        )

    return FileResponse(
        path=record.corrected_file_path,
        media_type=record.content_type,
        filename=record.corrected_filename,
        background=BackgroundTask(cleanup_job, store, job_id),
    )
