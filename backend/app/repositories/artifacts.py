"""Artifact repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact


async def add_artifact(session: AsyncSession, artifact: Artifact) -> Artifact:
    session.add(artifact)
    await session.flush()
    return artifact


async def get_artifact(
    session: AsyncSession,
    artifact_id: str,
    *,
    organization_id: str | None = None,
    workspace_id: str | None = None,
) -> Artifact | None:
    art = await session.get(Artifact, artifact_id)
    if art is None:
        return None
    if organization_id is not None and art.organization_id != organization_id:
        return None
    if workspace_id is not None and art.workspace_id != workspace_id:
        return None
    return art


async def list_artifacts(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str | None = None,
    kind: str | None = None,
    task_id: str | None = None,
    execution_id: str | None = None,
    verification_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Artifact], int]:
    base = select(Artifact).where(Artifact.organization_id == organization_id)
    if workspace_id:
        base = base.where(Artifact.workspace_id == workspace_id)
    if kind:
        base = base.where(Artifact.kind == kind)
    if task_id:
        base = base.where(Artifact.task_id == task_id)
    if execution_id:
        base = base.where(Artifact.execution_id == execution_id)
    if verification_status:
        base = base.where(Artifact.verification_status == verification_status)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = base.order_by(Artifact.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return rows, int(total)


async def list_for_execution(session: AsyncSession, execution_id: str) -> Sequence[Artifact]:
    res = await session.execute(
        select(Artifact).where(Artifact.execution_id == execution_id)
    )
    return res.scalars().all()
