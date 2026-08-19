from __future__ import annotations

import asyncio
import logging
import shutil

from src.jobs.store import JobStore

logger = logging.getLogger(__name__)


async def run_ttl_sweep(
    store: JobStore, ttl_seconds: int, interval_seconds: int
) -> None:
    """Long-running task (started via asyncio.create_task in the app
    lifespan, NOT FastAPI BackgroundTasks -- those only fire once per
    response and can't recur). Loops forever until cancelled: sleeps, then
    deletes any job whose temp dir + store entry has been idle (based on
    last-activity / updated_at, not created_at) past the TTL."""

    try:
        while True:
            await asyncio.sleep(interval_seconds)
            expired = await store.list_expired(ttl_seconds)
            removed = 0
            for record in expired:
                shutil.rmtree(record.temp_dir, ignore_errors=True)
                await store.delete(record.job_id)
                removed += 1
            if removed:
                logger.info("ttl_sweep removed_jobs=%d", removed)
    except asyncio.CancelledError:
        logger.info("ttl_sweep cancelled")
        raise
