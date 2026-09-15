"""Execution endpoints. Every command passes through the state machine."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DbDep, PrincipalDep
from app.api.serializers import execution_detail, execution_summary, step_out
from app.core.errors import not_found
from app.domain.enums import ActorType, EventType, TaskStatus
from app.orchestration import state_machine as sm
from app.repositories import executions as exec_repo
from app.repositories import plans as plans_repo
from app.schemas.common import Ack, Page
from app.schemas.execution import ExecutionDetail, ExecutionSummary
from app.schemas.plan import PlanStepOut
from app.services import event_service

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=Page[ExecutionSummary])
async def list_executions(
    session: DbDep,
    principal: PrincipalDep,
    workspace_id: str | None = None,
    status: str | None = None,
    task_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[ExecutionSummary]:
    rows, total = await exec_repo.list_executions(
        session,
        organization_id=principal.organization_id,
        workspace_id=workspace_id,
        status=status,
        task_id=task_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page[ExecutionSummary](
        items=[execution_summary(e) for e in rows], page=page, page_size=page_size, total=total
    )


async def _load(session, execution_id: str, principal):
    ex = await exec_repo.get_execution(
        session, execution_id, organization_id=principal.organization_id
    )
    if ex is None:
        raise not_found("Execution", execution_id)
    return ex


@router.get("/{execution_id}", response_model=ExecutionDetail)
async def get_execution(
    execution_id: str, session: DbDep, principal: PrincipalDep
) -> ExecutionDetail:
    ex = await _load(session, execution_id, principal)
    return await execution_detail(session, ex)


@router.get("/{execution_id}/steps", response_model=list[PlanStepOut])
async def get_steps(
    execution_id: str, session: DbDep, principal: PrincipalDep
) -> list[PlanStepOut]:
    ex = await _load(session, execution_id, principal)
    steps = await plans_repo.get_steps_for_plan(session, ex.plan_id) if ex.plan_id else []
    return [step_out(s) for s in steps]


@router.post("/{execution_id}/pause", response_model=Ack)
async def pause(execution_id: str, session: DbDep, principal: PrincipalDep) -> Ack:
    ex = await _load(session, execution_id, principal)
    sm.validate_transition(TaskStatus(ex.status), TaskStatus.BLOCKED)
    ex.status = TaskStatus.BLOCKED.value
    await event_service.emit(
        session,
        type=EventType.EXECUTION_PAUSED,
        execution_id=ex.id,
        task_id=ex.task_id,
        organization_id=ex.organization_id,
        workspace_id=ex.workspace_id,
        actor_type=ActorType.USER,
        label="Execution paused",
    )
    return Ack(message="Paused.")


@router.post("/{execution_id}/resume", response_model=Ack)
async def resume(execution_id: str, session: DbDep, principal: PrincipalDep) -> Ack:
    ex = await _load(session, execution_id, principal)
    sm.validate_transition(TaskStatus(ex.status), TaskStatus.RUNNING)
    ex.status = TaskStatus.RUNNING.value
    await event_service.emit(
        session,
        type=EventType.EXECUTION_RESUMED,
        execution_id=ex.id,
        task_id=ex.task_id,
        organization_id=ex.organization_id,
        workspace_id=ex.workspace_id,
        actor_type=ActorType.USER,
        label="Execution resumed",
    )
    from app.workers.queue import get_queue

    await get_queue().enqueue(
        {"job_type": "resume_execution", "task_id": ex.task_id, "execution_id": ex.id}
    )
    return Ack(message="Resumed.")


@router.post("/{execution_id}/cancel", response_model=Ack)
async def cancel(execution_id: str, session: DbDep, principal: PrincipalDep) -> Ack:
    ex = await _load(session, execution_id, principal)
    ex.cancel_requested = True
    await event_service.emit(
        session,
        type=EventType.TASK_CANCEL_REQUESTED,
        execution_id=ex.id,
        task_id=ex.task_id,
        organization_id=ex.organization_id,
        workspace_id=ex.workspace_id,
        actor_type=ActorType.USER,
        label="Cancellation requested",
    )
    return Ack(message="Cancellation requested.")
