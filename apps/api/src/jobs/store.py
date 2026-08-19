from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from src.exceptions import AppError
from src.models.detection import Detection
from src.models.block import TextBlock
from src.models.enums import FileType, JobStatus
from src.models.errors import ErrorCode


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    file_type: FileType
    original_path: str
    original_filename: str
    temp_dir: str
    blocks: list[TextBlock] = field(default_factory=list)
    detections: list[Detection] = field(default_factory=list)
    corrected_file_path: str | None = None
    corrected_filename: str | None = None
    content_type: str | None = None
    error: dict[str, str] | None = None
    parse_meta: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class JobStore:
    """In-memory job store. Guarded by a single asyncio.Lock held ONLY
    around dict mutation -- never across file I/O or LLM calls, both of
    which can take a long time and would otherwise serialize all job
    processing behind a single lock."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, **fields: Any) -> JobRecord:
        record = JobRecord(**fields)
        async with self._lock:
            self._jobs[record.job_id] = record
        return record

    async def get(self, job_id: str) -> JobRecord:
        async with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            raise AppError(
                ErrorCode.JOB_NOT_FOUND,
                f"Job {job_id} not found",
                http_status=404,
            )
        return record

    async def update(self, job_id: str, **fields: Any) -> JobRecord:
        async with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise AppError(
                    ErrorCode.JOB_NOT_FOUND,
                    f"Job {job_id} not found",
                    http_status=404,
                )
            for key, value in fields.items():
                setattr(record, key, value)
            record.updated_at = time.time()
        return record

    async def delete(self, job_id: str) -> None:
        async with self._lock:
            self._jobs.pop(job_id, None)

    async def list_expired(self, ttl_seconds: int) -> list[JobRecord]:
        cutoff = time.time() - ttl_seconds
        async with self._lock:
            return [r for r in self._jobs.values() if r.updated_at < cutoff]


def get_job_store(request: Request) -> JobStore:
    """FastAPI dependency exposing the store created in the app's lifespan
    context. Overridden in tests via app.dependency_overrides."""

    return request.app.state.job_store
