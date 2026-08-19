from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.exceptions import AppError
from src.jobs.store import JobStore
from src.jobs.ttl_sweep import run_ttl_sweep
from src.models.errors import ErrorDetail, ErrorResponse
from src.routers.jobs import router as jobs_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.job_store = JobStore()
    app.state.ttl_sweep_task = asyncio.create_task(
        run_ttl_sweep(
            app.state.job_store,
            settings.job_ttl_seconds,
            settings.ttl_sweep_interval_seconds,
        )
    )
    try:
        yield
    finally:
        app.state.ttl_sweep_task.cancel()
        try:
            await app.state.ttl_sweep_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="pii-compliance-agent API", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    logger.info(
        "method=%s path=%s status=%d duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=exc.code, message=exc.message))
    return JSONResponse(status_code=exc.http_status, content=body.model_dump())


app.include_router(jobs_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
