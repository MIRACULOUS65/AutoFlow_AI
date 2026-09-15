"""Task service — task creation, retrieval, listing, cancellation.

Creation is transactional: Task + Execution + context snapshot + task.created
event are persisted together, then a planning job is enqueued. The API returns
immediately; planning happens asynchronously (PRD §22, §61).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.db.base import new_id
from app.domain.enums import ActorType, EventType, TaskStatus
from app.models.execution import Execution, ExecutionContextSnapshotModel
from app.models.task import Task, TaskAttachment
from app.repositories import executions as exec_repo
from app.repositories import tasks as tasks_repo
from app.schemas.execution import ExecutionBudget
from app.schemas.task import TaskRequest
from app.services import audit_service, event_service
from app.workers.queue import get_queue


def _derive_name(goal: str) -> str:
    words = goal.strip().split()
    name = " ".join(words[:6]).rstrip(".,")
    if len(name) > 60:
        name = name[:60].rstrip() + "…"
    return name or "New Task"


async def create_task(
    session: AsyncSession,
    *,
    principal: Principal,
    request: TaskRequest,
) -> tuple[Task, Execution]:
    goal = request.resolved_goal

    task = Task(
        organization_id=principal.organization_id,
        workspace_id=request.workspace_id,
        created_by=principal.user_id,
        name=_derive_name(goal),
        goal=goal,
        constraints=[c.model_dump() for c in request.constraints],
        client_metadata=request.client_metadata,
        priority=request.priority,
        status=TaskStatus.QUEUED.value,
    )
    await tasks_repo.add_task(session, task)

    for att in request.attachments:
        session.add(
            TaskAttachment(
                task_id=task.id,
                filename=att.filename or att.file_id or att.attachment_id or "attachment",
                mime_type=att.mime_type,
                size=att.size,
                content_hash=att.content_hash,
                source="client",
            )
        )

    execution = Execution(
        task_id=task.id,
        organization_id=principal.organization_id,
        workspace_id=request.workspace_id,
        status=TaskStatus.QUEUED.value,
        budget=ExecutionBudget().model_dump(),
    )
    await exec_repo.add_execution(session, execution)

    task.current_execution_id = execution.id

    # Deterministic context snapshot (PRD §45).
    snapshot = ExecutionContextSnapshotModel(
        execution_id=execution.id,
        organization_id=principal.organization_id,
        workspace_id=request.workspace_id,
        permissions=[r.value for r in principal.roles],
        policy_profile="standard",
        tool_allowlist=[],
        context_namespace=f"ctx_{execution.id}",
        budget=ExecutionBudget().model_dump(),
    )
    await exec_repo.add_context_snapshot(session, snapshot)

    await event_service.emit(
        session,
        type=EventType.TASK_CREATED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=principal.organization_id,
        workspace_id=request.workspace_id,
        actor_type=ActorType.USER,
        label="Task created",
        payload={"goal": goal},
    )
    await audit_service.record(
        session,
        action="task.created",
        resource_type="task",
        resource_id=task.id,
        actor=principal.user_id,
        organization_id=principal.organization_id,
        workspace_id=request.workspace_id,
    )

    return task, execution


async def enqueue_planning(task_id: str, execution_id: str) -> None:
    await get_queue().enqueue(
        {
            "job_type": "plan_task",
            "task_id": task_id,
            "execution_id": execution_id,
        }
    )


async def get_task(
    session: AsyncSession, task_id: str, *, principal: Principal
) -> Task | None:
    return await tasks_repo.get_task(
        session,
        task_id,
        organization_id=principal.organization_id,
    )


async def list_tasks(
    session: AsyncSession,
    *,
    principal: Principal,
    workspace_id: str | None = None,
    status: str | None = None,
    created_by: str | None = None,
    search: str | None = None,
    priority: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Task], int]:
    return await tasks_repo.list_tasks(
        session,
        organization_id=principal.organization_id,
        workspace_id=workspace_id,
        status=status,
        created_by=created_by,
        search=search,
        priority=priority,
        limit=limit,
        offset=offset,
    )


async def request_cancel(
    session: AsyncSession, task: Task, *, principal: Principal
) -> None:
    """Persist a cancellation request. The worker observes it before the next
    side effect and transitions to CANCELLED (PRD §26, §54)."""
    if task.current_execution_id:
        execution = await exec_repo.get_execution(session, task.current_execution_id)
        if execution is not None:
            execution.cancel_requested = True
            await event_service.emit(
                session,
                type=EventType.TASK_CANCEL_REQUESTED,
                execution_id=execution.id,
                task_id=task.id,
                organization_id=task.organization_id,
                workspace_id=task.workspace_id,
                actor_type=ActorType.USER,
                label="Cancellation requested",
            )
    await audit_service.record(
        session,
        action="task.cancel_requested",
        resource_type="task",
        resource_id=task.id,
        actor=principal.user_id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
    )
