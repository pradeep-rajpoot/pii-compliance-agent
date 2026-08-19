import time

import pytest

from src.exceptions import AppError
from src.jobs.store import JobStore
from src.models.enums import FileType, JobStatus


@pytest.mark.asyncio
async def test_create_and_get():
    store = JobStore()
    record = await store.create(
        job_id="j1",
        status=JobStatus.QUEUED,
        file_type=FileType.CSV,
        original_path="/tmp/x/original.csv",
        original_filename="x.csv",
        temp_dir="/tmp/x",
    )

    fetched = await store.get("j1")
    assert fetched is record
    assert fetched.status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_get_missing_raises_job_not_found():
    store = JobStore()
    with pytest.raises(AppError) as exc_info:
        await store.get("does-not-exist")
    assert exc_info.value.http_status == 404


@pytest.mark.asyncio
async def test_update_bumps_updated_at():
    store = JobStore()
    record = await store.create(
        job_id="j1",
        status=JobStatus.QUEUED,
        file_type=FileType.CSV,
        original_path="/tmp/x/original.csv",
        original_filename="x.csv",
        temp_dir="/tmp/x",
    )
    original_updated_at = record.updated_at
    time.sleep(0.01)

    updated = await store.update("j1", status=JobStatus.DETECTING)

    assert updated.status == JobStatus.DETECTING
    assert updated.updated_at > original_updated_at


@pytest.mark.asyncio
async def test_delete_removes_job():
    store = JobStore()
    await store.create(
        job_id="j1",
        status=JobStatus.QUEUED,
        file_type=FileType.CSV,
        original_path="/tmp/x/original.csv",
        original_filename="x.csv",
        temp_dir="/tmp/x",
    )
    await store.delete("j1")
    with pytest.raises(AppError):
        await store.get("j1")


@pytest.mark.asyncio
async def test_list_expired_based_on_updated_at_not_created_at():
    store = JobStore()
    record = await store.create(
        job_id="j1",
        status=JobStatus.QUEUED,
        file_type=FileType.CSV,
        original_path="/tmp/x/original.csv",
        original_filename="x.csv",
        temp_dir="/tmp/x",
    )
    # Make it look old by created_at, but touch it via update() so
    # updated_at is fresh -- it should NOT be considered expired.
    record.created_at = time.time() - 10_000
    await store.update("j1", status=JobStatus.DETECTING)

    expired = await store.list_expired(ttl_seconds=1)
    assert expired == []

    # Now force updated_at itself to be old -- it SHOULD be expired.
    record.updated_at = time.time() - 10_000
    expired = await store.list_expired(ttl_seconds=1)
    assert len(expired) == 1
    assert expired[0].job_id == "j1"
