"""Aggregate v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    approvals,
    artifacts,
    auth,
    events,
    executions,
    knowledge,
    plans,
    tasks,
    workflows,
    workspaces,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(workspaces.router)
api_router.include_router(tasks.router)
api_router.include_router(plans.router)
api_router.include_router(executions.router)
api_router.include_router(approvals.router)
api_router.include_router(artifacts.router)
api_router.include_router(events.router)
api_router.include_router(agents.router)
api_router.include_router(workflows.router)
api_router.include_router(knowledge.router)
