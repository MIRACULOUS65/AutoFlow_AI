"""Plan endpoints. Plans are read-only through the desktop API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbDep, PrincipalDep
from app.api.serializers import plan_detail, plan_summary
from app.core.errors import not_found
from app.repositories import plans as plans_repo
from app.repositories import tasks as tasks_repo
from app.schemas.plan import PlanDetail, PlanSummary

router = APIRouter(tags=["plans"])


async def _require_task(session, task_id: str, principal):
    task = await tasks_repo.get_task(
        session, task_id, organization_id=principal.organization_id
    )
    if task is None:
        raise not_found("Task", task_id)
    return task


@router.get("/tasks/{task_id}/plans", response_model=list[PlanSummary])
async def list_plans(task_id: str, session: DbDep, principal: PrincipalDep) -> list[PlanSummary]:
    await _require_task(session, task_id, principal)
    plans = await plans_repo.list_plans(session, task_id)
    return [plan_summary(p) for p in plans]


@router.get("/tasks/{task_id}/plans/{version}", response_model=PlanDetail)
async def get_plan_version(
    task_id: str, version: int, session: DbDep, principal: PrincipalDep
) -> PlanDetail:
    await _require_task(session, task_id, principal)
    plan = await plans_repo.get_plan_by_version(session, task_id, version)
    if plan is None:
        raise not_found("Plan version", str(version))
    return await plan_detail(session, plan)
