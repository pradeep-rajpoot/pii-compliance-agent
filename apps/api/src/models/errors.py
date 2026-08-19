from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class ErrorCode(StrEnum):
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    PARSE_ERROR = "PARSE_ERROR"
    LLM_ERROR = "LLM_ERROR"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"

    # Needed but not enumerated in the spec's §9.5 error list:
    INVALID_JOB_STATE = "INVALID_JOB_STATE"  # 409 on /correct in the wrong state
    FILE_NOT_READY = "FILE_NOT_READY"  # 404 on /download before status=="corrected"
    CORRECTION_ERROR = "CORRECTION_ERROR"  # correction agent failed


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    status: Literal["failed"] = "failed"
    error: ErrorDetail
