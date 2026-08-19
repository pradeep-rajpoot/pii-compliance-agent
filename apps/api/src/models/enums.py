from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    DETECTING = "detecting"
    DETECTED = "detected"
    CORRECTING = "correcting"
    CORRECTED = "corrected"
    FAILED = "failed"


class FileType(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"
    DOCX = "docx"
    JSON = "json"
