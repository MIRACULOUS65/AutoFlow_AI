"""Workspace repository (thin; shares tenancy helpers with organizations)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.repositories.organizations import (  # re-exported for convenience
    get_workspace,
    list_workspaces,
    user_can_access_workspace,
)

__all__ = [
    "get_workspace",
    "list_workspaces",
    "user_can_access_workspace",
    "create_workspace",
]


async def create_workspace(
    session: AsyncSession,
    *,
    organization_id: str,
    name: str,
    policy_profile: str = "standard",
    capabilities: list[str] | None = None,
) -> Workspace:
    ws = Workspace(
        organization_id=organization_id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        policy_profile=policy_profile,
        capabilities=capabilities or [],
    )
    session.add(ws)
    await session.flush()
    return ws
