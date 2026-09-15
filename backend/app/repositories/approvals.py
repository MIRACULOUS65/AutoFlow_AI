"""Approval + evidence repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval, ApprovalEvidence


async def add_approval(session: AsyncSession, approval: Approval) -> Approval:
    session.add(approval)
    await session.flush()
    return approval


async def add_evidence(session: AsyncSession, evidence: ApprovalEvidence) -> ApprovalEvidence:
    session.add(evidence)
    await session.flush()
    return evidence


async def get_approval(
    session: AsyncSession,
    approval_id: str,
    *,
    organization_id: str | None = None,
    workspace_id: str | None = None,
) -> Approval | None:
    ap = await session.get(Approval, approval_id)
    if ap is None:
        return None
    if organization_id is not None and ap.organization_id != organization_id:
        return None
    if workspace_id is not None and ap.workspace_id != workspace_id:
        return None
    return ap


async def get_evidence(session: AsyncSession, approval_id: str) -> Sequence[ApprovalEvidence]:
    res = await session.execute(
        select(ApprovalEvidence).where(ApprovalEvidence.approval_id == approval_id)
    )
    return res.scalars().all()


async def list_approvals(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str | None = None,
    status: str | None = None,
    risk_class: str | None = None,
    task_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Approval], int]:
    base = select(Approval).where(Approval.organization_id == organization_id)
    if workspace_id:
        base = base.where(Approval.workspace_id == workspace_id)
    if status:
        base = base.where(Approval.status == status)
    if risk_class:
        base = base.where(Approval.risk_class == risk_class)
    if task_id:
        base = base.where(Approval.task_id == task_id)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = base.order_by(Approval.requested_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return rows, int(total)


async def find_pending_by_action_hash(
    session: AsyncSession, execution_id: str, action_hash: str
) -> Approval | None:
    res = await session.execute(
        select(Approval).where(
            Approval.execution_id == execution_id,
            Approval.action_hash == action_hash,
            Approval.status == "PENDING",
        )
    )
    return res.scalar_one_or_none()
