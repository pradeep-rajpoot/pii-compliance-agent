from __future__ import annotations

from pydantic import BaseModel

from src.models.block import TextBlock
from src.models.detection import Detection
from src.models.enums import FileType, JobStatus
from src.models.errors import ErrorDetail


class JobResponse(BaseModel):
    """Matches spec §9.2 exactly."""

    job_id: str
    status: JobStatus
    file_type: FileType
    blocks: list[TextBlock]
    detections: list[Detection]
    error: ErrorDetail | None = None
