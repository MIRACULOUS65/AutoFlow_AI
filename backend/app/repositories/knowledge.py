"""Knowledge source repository (metadata only; authorization independent of retrieval)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_source import KnowledgeSource


async def get_source(
    session: AsyncSession,
    source_id: str,
    *,
    organization_id: str | None = None,
    workspace_id: str | None = None,
) -> KnowledgeSource | None:
    src = await session.get(KnowledgeSource, source_id)
    if src is None:
        return None
    if organization_id is not None and src.organization_id != organization_id:
        return None
    if workspace_id is not None and src.workspace_id != workspace_id:
        return None
    return src


async def list_sources(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[KnowledgeSource], int]:
    base = select(KnowledgeSource).where(
        KnowledgeSource.organization_id == organization_id
    )
    if workspace_id:
        base = base.where(KnowledgeSource.workspace_id == workspace_id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = base.order_by(KnowledgeSource.updated_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return rows, int(total)
