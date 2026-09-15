"""Organization + workspace + membership repositories (tenancy roots)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import WorkspaceMembership
from app.models.organization import Organization
from app.models.workspace import Workspace


async def get_organization(session: AsyncSession, organization_id: str) -> Organization | None:
    return await session.get(Organization, organization_id)


async def list_organizations(session: AsyncSession) -> list[Organization]:
    res = await session.execute(select(Organization).order_by(Organization.created_at))
    return list(res.scalars().all())


async def get_workspace(
    session: AsyncSession, workspace_id: str, organization_id: str | None = None
) -> Workspace | None:
    ws = await session.get(Workspace, workspace_id)
    if ws is None:
        return None
    if organization_id is not None and ws.organization_id != organization_id:
        return None
    return ws


async def list_workspaces(
    session: AsyncSession, organization_id: str
) -> list[Workspace]:
    res = await session.execute(
        select(Workspace)
        .where(Workspace.organization_id == organization_id)
        .order_by(Workspace.created_at)
    )
    return list(res.scalars().all())


async def user_can_access_workspace(
    session: AsyncSession, user_id: str, workspace_id: str
) -> bool:
    res = await session.execute(
        select(WorkspaceMembership.id).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.status == "ACTIVE",
        )
    )
    return res.scalar_one_or_none() is not None
