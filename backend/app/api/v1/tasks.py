"""Task endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, Query

from app.api.deps import DbDep, PrincipalDep
from app.api.serializers import task_detail, task_summary
from app.core.errors import conflict, not_found
from app.core.security import request_hash
from app.domain.enums import Role
from app.repositories import idempotency as idem_repo
from app.schemas.common import Ack, Page
from app.schemas.task import TaskCreateResponse, TaskDetail, TaskRequest, TaskSummary
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskCreateResponse, status_code=201)
async def create_task(
    body: TaskRequest,
    session: DbDep,
    principal: PrincipalDep,
    background: BackgroundTasks,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TaskCreateResponse:
    if principal.has_role(Role.VIEWER) and not principal.has_role(
        Role.OPERATOR, Role.ADMIN, Role.OWNER
    ):
        from app.core.errors import forbidden

        raise forbidden("Viewers cannot create tasks.")

    route = "POST /tasks"
    req_hash = request_hash(body.model_dump(mode="json"))

    if idempotency_key:
        existing = await idem_repo.get_key(
            session, principal_id=principal.user_id, route=route, key=idempotency_key
        )
        if existing is not None:
            if existing.request_hash != req_hash:
                raise conflict(
                    "Idempotency-Key reused with a different request body.",
                    details={"idempotency_key": idempotency_key},
                )
            return TaskCreateResponse(**existing.response)

    task, execution = await task_service.create_task(
        session, principal=principal, request=body
    )
    response = TaskCreateResponse(
        task_id=task.id, execution_id=execution.id, status=task.status, created_at=task.created_at
    )

    if idempotency_key:
        await idem_repo.store_key(
            session,
            principal_id=principal.user_id,
            route=route,
            key=idempotency_key,
            request_hash=req_hash,
            response=response.model_dump(mode="json"),
        )

    # Planning is enqueued after the request transaction commits so the worker
    # (which uses its own session) can read the persisted task.
    background.add_task(task_service.enqueue_planning, task.id, execution.id)
    return response


@router.get("", response_model=Page[TaskSummary])
async def list_tasks(
    session: DbDep,
    principal: PrincipalDep,
    workspace_id: str | None = None,
    status: str | None = None,
    created_by: str | None = None,
    search: str | None = None,
    priority: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[TaskSummary]:
    rows, total = await task_service.list_tasks(
        session,
        principal=principal,
        workspace_id=workspace_id,
        status=status,
        created_by=created_by,
        search=search,
        priority=priority,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page[TaskSummary](
        items=[task_summary(t) for t in rows], page=page, page_size=page_size, total=total
    )


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(task_id: str, session: DbDep, principal: PrincipalDep) -> TaskDetail:
    task = await task_service.get_task(session, task_id, principal=principal)
    if task is None:
        raise not_found("Task", task_id)
    return await task_detail(session, task)


@router.post("/{task_id}/cancel", response_model=Ack)
async def cancel_task(task_id: str, session: DbDep, principal: PrincipalDep) -> Ack:
    task = await task_service.get_task(session, task_id, principal=principal)
    if task is None:
        raise not_found("Task", task_id)
    await task_service.request_cancel(session, task, principal=principal)
    return Ack(message="Cancellation requested.")
