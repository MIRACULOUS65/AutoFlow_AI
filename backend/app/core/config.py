"""Application configuration.

All configuration is environment-driven. The runtime *mode* switches (mock vs
real) live here so the control plane can boot fully with mocks today and swap in
real implementations later without touching the API or database layer.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Mode = Literal["mock", "real"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    autoflow_env: str = "development"

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Persistence. SQLite dev default keeps the backend runnable with no infra;
    # PostgreSQL is the production path (same SQLAlchemy async interface).
    database_url: str = "sqlite+aiosqlite:///./autoflow.db"

    # Queue. Empty => in-process queue. A redis:// URL => Redis-backed queue.
    redis_url: str = ""

    # Component modes.
    auth_mode: Mode = "mock"
    orchestrator_mode: Mode = "mock"
    agent_runtime_mode: Mode = "mock"
    tool_runtime_mode: Mode = "mock"
    verifier_mode: Mode = "mock"
    recovery_mode: Mode = "mock"
    policy_mode: Mode = "mock"

    # Intelligence integration. "mock" = built-in mock runtimes; "integration"
    # = the real AI/ML runtime reached out-of-process over its HTTP server.
    intelligence_mode: Literal["mock", "integration"] = "mock"
    ai_ml_enabled: bool = True
    ai_ml_url: str = "http://127.0.0.1:8770"
    ai_ml_timeout_seconds: int = 120
    ai_ml_use_model: bool = False  # True => AI/ML plans with real LLMs

    artifact_storage_mode: Literal["local", "s3"] = "local"
    artifact_storage_dir: str = "./artifacts"

    run_inline_worker: bool = True

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "app://.",
        ]
    )

    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.autoflow_env.lower() in {"production", "prod"}

    @property
    def use_real_intelligence(self) -> bool:
        """Whether the real AI/ML runtime should back the intelligence seam.

        True when integration mode is selected AND the AI/ML runtime is enabled.
        The legacy per-component ``*_mode == "real"`` switches also imply this.
        """
        if not self.ai_ml_enabled:
            return False
        if self.intelligence_mode == "integration":
            return True
        return self.orchestrator_mode == "real"

    @property
    def uses_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def sync_database_url(self) -> str:
        """Synchronous URL used by Alembic migrations."""
        return (
            self.database_url.replace("+aiosqlite", "")
            .replace("+asyncpg", "")
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
