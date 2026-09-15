"""Workflow + workflow-version repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow, WorkflowVersion


async def get_workflow(
    session: AsyncSession,
    workflow_id: str,
    *,
    organization_id: str | None = None,
    workspace_id: str | None = None,
) -> Workflow | None:
    wf = await session.get(Workflow, workflow_id)
    if wf is None:
        return None
    if organization_id is not None and wf.organization_id != organization_id:
        return None
    if workspace_id is not None and wf.workspace_id != workspace_id:
        return None
    return wf


async def list_workflows(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Workflow], int]:
    base = select(Workflow).where(Workflow.organization_id == organization_id)
    if workspace_id:
        base = base.where(Workflow.workspace_id == workspace_id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = base.order_by(Workflow.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return rows, int(total)


async def list_versions(session: AsyncSession, workflow_id: str) -> Sequence[WorkflowVersion]:
    res = await session.execute(
        select(WorkflowVersion)
        .where(WorkflowVersion.workflow_id == workflow_id)
        .order_by(WorkflowVersion.created_at)
    )
    return res.scalars().all()
