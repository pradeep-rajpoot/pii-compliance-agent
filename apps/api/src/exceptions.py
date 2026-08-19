from __future__ import annotations

from src.models.errors import ErrorCode


class AppError(Exception):
    """Application-level error carrying an ErrorCode and the HTTP status it
    should be surfaced as. Caught by a global FastAPI exception handler
    (see src/main.py) which serializes it into the ErrorResponse shape
    required by spec §9.5."""

    def __init__(self, code: ErrorCode, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
