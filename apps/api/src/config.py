"""Application configuration.

All values are read from environment variables (optionally via a `.env` file).
BEDROCK_REGION and BEDROCK_MODEL_ID have no defaults: the app must fail fast at
startup if they are not configured, rather than silently falling back to some
region/model that may not match the deployer's AWS account.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Bedrock / LLM ---------------------------------------------------
    bedrock_region: str = Field(alias="BEDROCK_REGION")
    bedrock_model_id: str = Field(alias="BEDROCK_MODEL_ID")
    llm_timeout_seconds: float = Field(default=60.0, alias="LLM_TIMEOUT_SECONDS")

    # --- Upload / job limits ----------------------------------------------
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    job_ttl_seconds: int = Field(default=1800, alias="JOB_TTL_SECONDS")
    ttl_sweep_interval_seconds: int = Field(
        default=600, alias="TTL_SWEEP_INTERVAL_SECONDS"
    )

    # --- Detection chunking -------------------------------------------------
    detection_chunk_char_limit: int = Field(
        default=8000, alias="DETECTION_CHUNK_CHAR_LIMIT"
    )
    detection_max_blocks_per_chunk: int = Field(
        default=20, alias="DETECTION_MAX_BLOCKS_PER_CHUNK"
    )
    detection_max_chunks_per_job: int = Field(
        default=50, alias="DETECTION_MAX_CHUNKS_PER_JOB"
    )

    # --- CORS ---------------------------------------------------------------
    cors_allow_origins: str = Field(
        default="http://localhost:3000", alias="CORS_ALLOW_ORIGINS"
    )

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor.

    Raises a pydantic ValidationError (clear, structured message) at first
    access if required env vars are missing -- this is the "fail fast" the
    build spec asks for. Cached so we don't re-parse env on every call, but
    tests can call `get_settings.cache_clear()` after monkeypatching env vars.
    """

    return Settings()  # type: ignore[call-arg]
