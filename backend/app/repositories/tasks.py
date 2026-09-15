"""Task + attachment repository. Every read is tenancy-scoped."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskAttachment


async def add_task(session: AsyncSession, task: Task) -> Task:
    session.add(task)
    await session.flush()
    return task


async def get_task(
    session: AsyncSession,
    task_id: str,
    *,
    organization_id: str,
    workspace_id: str | None = None,
) -> Task | None:
    task = await session.get(Task, task_id)
    if task is None:
        return None
    if task.organization_id != organization_id:
        return None
    if workspace_id is not None and task.workspace_id != workspace_id:
        return None
    return task


def _apply_task_filters(
    stmt: Select,
    *,
    organization_id: str,
    workspace_id: str | None,
    status: str | None,
    created_by: str | None,
    search: str | None,
    priority: int | None,
) -> Select:
    stmt = stmt.where(Task.organization_id == organization_id)
    if workspace_id:
        stmt = stmt.where(Task.workspace_id == workspace_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if created_by:
        stmt = stmt.where(Task.created_by == created_by)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(func.lower(Task.name).like(like), func.lower(Task.goal).like(like))
        )
    return stmt


async def list_tasks(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str | None = None,
    status: str | None = None,
    created_by: str | None = None,
    search: str | None = None,
    priority: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Task], int]:
    filters = dict(
        organization_id=organization_id,
        workspace_id=workspace_id,
        status=status,
        created_by=created_by,
        search=search,
        priority=priority,
    )
    count_stmt = _apply_task_filters(select(func.count(Task.id)), **filters)
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = _apply_task_filters(select(Task), **filters)
    stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return rows, int(total)


async def get_attachments(session: AsyncSession, task_id: str) -> Sequence[TaskAttachment]:
    res = await session.execute(
        select(TaskAttachment).where(TaskAttachment.task_id == task_id)
    )
    return res.scalars().all()
