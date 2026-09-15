"""Workspace + organization endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbDep, PrincipalDep
from app.core.errors import not_found
from app.repositories import organizations as orgs_repo
from app.schemas.workspace import OrganizationOut, WorkspaceOut

router = APIRouter(tags=["workspaces"])


@router.get("/organizations", response_model=list[OrganizationOut])
async def list_organizations(session: DbDep, principal: PrincipalDep) -> list[OrganizationOut]:
    orgs = await orgs_repo.list_organizations(session)
    return [
        OrganizationOut(id=o.id, name=o.name, status=o.status, created_at=o.created_at)
        for o in orgs
        if o.id == principal.organization_id
    ]


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(session: DbDep, principal: PrincipalDep) -> list[WorkspaceOut]:
    workspaces = await orgs_repo.list_workspaces(session, principal.organization_id)
    return [_to_out(w) for w in workspaces]


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: str, session: DbDep, principal: PrincipalDep
) -> WorkspaceOut:
    ws = await orgs_repo.get_workspace(
        session, workspace_id, organization_id=principal.organization_id
    )
    if ws is None:
        raise not_found("Workspace", workspace_id)
    return _to_out(ws)


def _to_out(ws) -> WorkspaceOut:
    return WorkspaceOut(
        id=ws.id,
        organization_id=ws.organization_id,
        name=ws.name,
        slug=ws.slug,
        description=ws.description,
        policy_profile=ws.policy_profile,
        capabilities=ws.capabilities or [],
        members=ws.members,
        created_at=ws.created_at,
    )
