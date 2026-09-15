"""Shared test fixtures.

Each test module gets a fresh in-memory-ish SQLite file DB and an ASGI client
bound to the app. The inline worker is disabled; tests drive the worker's
handle_job directly so execution is deterministic (no timing races).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

# Configure environment BEFORE importing app modules (settings is cached).
_TMP_DB = os.path.join(tempfile.gettempdir(), "autoflow_test.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["RUN_INLINE_WORKER"] = "false"
os.environ["REDIS_URL"] = ""
os.environ["ARTIFACT_STORAGE_DIR"] = os.path.join(tempfile.gettempdir(), "autoflow_test_artifacts")
# Pin the intelligence seam to MOCK for the baseline suite regardless of the
# developer's ambient shell (a leaked INTELLIGENCE_MODE=integration would
# otherwise silently route the mock tests through the real AI/ML runtime).
# Integration tests opt back in explicitly via their own fixtures.
os.environ["INTELLIGENCE_MODE"] = "mock"
os.environ["ORCHESTRATOR_MODE"] = "mock"


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session so the shared async engine
    and in-process queue remain bound to a live loop."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_reset() -> AsyncGenerator[None, None]:
    """Reset schema per test on a shared engine.

    We drop + recreate all tables rather than disposing the engine each test.
    Disposing the async SQLite engine mid-suite races the aiosqlite worker
    thread against a closing event loop on Windows, so we keep one engine and
    just clear its data between tests.
    """
    from app.db.base import Base
    from app.db.session import get_engine
    from app.workers.queue import reset_queue

    import app.models  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    reset_queue()
    yield


@pytest_asyncio.fixture
async def client(db_reset) -> AsyncGenerator:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer dev"},
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded(db_reset) -> AsyncGenerator[None, None]:
    from app.db.seed import seed

    await seed(force=True)
    yield
