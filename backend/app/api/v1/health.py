"""Health, readiness, version endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import API_VERSION, CONTRACT_VERSION, __version__
from app.core.config import settings
from app.db.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict:
    checks = {"database": False}
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    ready = all(checks.values())
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@router.get("/version")
async def version() -> dict:
    return {
        "backend_version": __version__,
        "api_version": API_VERSION,
        "contract_version": CONTRACT_VERSION,
        "modes": {
            "auth": settings.auth_mode,
            "orchestrator": settings.orchestrator_mode,
            "agent_runtime": settings.agent_runtime_mode,
            "tool_runtime": settings.tool_runtime_mode,
            "verifier": settings.verifier_mode,
            "recovery": settings.recovery_mode,
            "policy": settings.policy_mode,
        },
    }
