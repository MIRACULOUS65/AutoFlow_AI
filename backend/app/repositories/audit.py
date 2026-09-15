"""Audit log repository (append-oriented)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def add_audit(session: AsyncSession, record: AuditLog) -> AuditLog:
    session.add(record)
    await session.flush()
    return record


async def list_audit(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str | None = None,
    resource_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[AuditLog], int]:
    base = select(AuditLog).where(AuditLog.organization_id == organization_id)
    if workspace_id:
        base = base.where(AuditLog.workspace_id == workspace_id)
    if resource_id:
        base = base.where(AuditLog.resource_id == resource_id)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = base.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return rows, int(total)
