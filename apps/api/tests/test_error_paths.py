import time

from src.config import get_settings


def _poll_until(client, job_id, terminal_statuses, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] in terminal_statuses:
            return last
        time.sleep(0.02)
    raise AssertionError(f"job never reached {terminal_statuses}, last={last}")


def test_unsupported_file_type_rejected(client, fixtures_dir):
    with open(fixtures_dir / "unsupported.txt", "rb") as f:
        resp = client.post(
            "/api/jobs/detect",
            files={"file": ("unsupported.txt", f, "text/plain")},
        )
    assert resp.status_code == 415
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_legacy_doc_extension_rejected(client, fixtures_dir):
    with open(fixtures_dir / "legacy.doc", "rb") as f:
        resp = client.post(
            "/api/jobs/detect",
            files={"file": ("legacy.doc", f, "application/msword")},
        )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_file_too_large_rejected(client, fixtures_dir, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "50")
    get_settings.cache_clear()

    with open(fixtures_dir / "sample.docx", "rb") as f:
        resp = client.post(
            "/api/jobs/detect",
            files={
                "file": (
                    "sample.docx",
                    f,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_job_not_found_returns_404(client):
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"


def test_correct_in_wrong_state_returns_409(client, mock_bedrock, fixtures_dir):
    # Force the detection agent to fail fast (rather than reach "detected"),
    # so the job is deterministically NOT in "detected" state when we call
    # /correct -- exercising the 409 guard regardless of which non-detected
    # state ("failed" here) the job actually landed in.
    mock_bedrock.set_exception(TimeoutError("simulated llm timeout"))

    with open(fixtures_dir / "sample.csv", "rb") as f:
        resp = client.post(
            "/api/jobs/detect",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    job_id = resp.json()["job_id"]
    _poll_until(client, job_id, {"detected", "failed"})

    resp = client.post(f"/api/jobs/{job_id}/correct")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_JOB_STATE"


def test_download_before_corrected_returns_404(client, mock_bedrock, fixtures_dir):
    mock_bedrock.set_responses([[]])
    with open(fixtures_dir / "sample.csv", "rb") as f:
        resp = client.post(
            "/api/jobs/detect",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    job_id = resp.json()["job_id"]
    _poll_until(client, job_id, {"detected", "failed"})

    resp = client.get(f"/api/jobs/{job_id}/download")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "FILE_NOT_READY"


def test_llm_error_after_retries_exhausted(client, mock_bedrock, fixtures_dir):
    mock_bedrock.set_exception(TimeoutError("simulated llm timeout"))

    with open(fixtures_dir / "sample.csv", "rb") as f:
        resp = client.post(
            "/api/jobs/detect",
            files={"file": ("sample.csv", f, "text/csv")},
        )
    job_id = resp.json()["job_id"]

    failed = _poll_until(client, job_id, {"detected", "failed"})
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "LLM_ERROR"
    assert len(mock_bedrock.calls) == 2  # one initial try + exactly one retry
