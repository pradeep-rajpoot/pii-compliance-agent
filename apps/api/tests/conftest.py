from __future__ import annotations

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# --- required env vars must be set BEFORE src.config/src.main is imported ---
os.environ.setdefault("BEDROCK_REGION", "us-east-1")
os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-test")
os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://localhost:3000")

from src.config import get_settings  # noqa: E402
from src.jobs.store import JobStore, get_job_store  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def job_store() -> JobStore:
    return JobStore()


@pytest.fixture
def app(monkeypatch, job_store):
    # Disable the periodic TTL sweep for tests: it's not something any test
    # here needs to exercise, and we don't want a real background loop
    # ticking during the test run.
    async def _noop_sweep(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise

    monkeypatch.setattr("src.main.run_ttl_sweep", _noop_sweep)

    from src.main import app as fastapi_app

    fastapi_app.dependency_overrides[get_job_store] = lambda: job_store
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


class FakeToolUseBlock:
    def __init__(self, detections: list[dict]):
        self.type = "tool_use"
        self.input = {"detections": detections}


class FakeMessage:
    def __init__(self, detections: list[dict]):
        self.content = [FakeToolUseBlock(detections)]


@pytest.fixture
def mock_bedrock(monkeypatch):
    """Patches the detection agent's Bedrock client construction point
    (src.agents.detection_agent.build_client) so no automated test ever
    calls real Bedrock. Returns a small controller object:

        mock_bedrock.set_responses([[{...raw detection dict...}], [...]])

    supplies one list-of-raw-detection-dicts per chunk/call, in call order.
    Defaults to returning no detections for any call if never configured.
    """

    state = {"responses": None, "exception": None}
    calls: list[str] = []

    async def fake_create(**kwargs):
        idx = len(calls)
        calls.append(kwargs.get("messages", [{}])[0].get("content", ""))
        if state["exception"] is not None:
            raise state["exception"]
        responses = state["responses"]
        if not responses:
            return FakeMessage([])
        i = min(idx, len(responses) - 1)
        return FakeMessage(responses[i])

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))

    def build_client_stub():
        return fake_client

    monkeypatch.setattr(
        "src.agents.detection_agent.build_client", build_client_stub
    )

    controller = SimpleNamespace(
        set_responses=lambda responses: state.__setitem__("responses", responses),
        set_exception=lambda exc: state.__setitem__("exception", exc),
        client=fake_client,
        calls=calls,
    )
    return controller


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
