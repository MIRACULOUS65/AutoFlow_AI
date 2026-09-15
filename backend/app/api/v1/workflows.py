"""Workflow endpoints (read-only; versions immutable)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import DbDep, PrincipalDep
from app.core.errors import not_found
from app.repositories import executions as exec_repo
from app.repositories import workflows as workflows_repo
from app.schemas.common import Page, Schema

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowOut(Schema):
    id: str
    workspace_id: str
    name: str
    purpose: str
    current_version: str
    runs: int
    success_rate: int
    last_verified_at: datetime | None = None
    agent_ids: list[str] = []
    step_titles: list[str] = []
    artifact_ids: list[str] = []


def _out(w) -> WorkflowOut:
    return WorkflowOut(
        id=w.id,
        workspace_id=w.workspace_id,
        name=w.name,
        purpose=w.purpose,
        current_version=w.current_version,
        runs=w.runs,
        success_rate=w.success_rate,
        last_verified_at=w.last_verified_at,
        agent_ids=w.agent_ids or [],
        step_titles=w.step_titles or [],
        artifact_ids=w.artifact_ids or [],
    )


@router.get("", response_model=Page[WorkflowOut])
async def list_workflows(
    session: DbDep,
    principal: PrincipalDep,
    workspace_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[WorkflowOut]:
    rows, total = await workflows_repo.list_workflows(
        session,
        organization_id=principal.organization_id,
        workspace_id=workspace_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page[WorkflowOut](
        items=[_out(w) for w in rows], page=page, page_size=page_size, total=total
    )


async def _require(session, workflow_id: str, principal):
    wf = await workflows_repo.get_workflow(
        session, workflow_id, organization_id=principal.organization_id
    )
    if wf is None:
        raise not_found("Workflow", workflow_id)
    return wf


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(workflow_id: str, session: DbDep, principal: PrincipalDep) -> WorkflowOut:
    return _out(await _require(session, workflow_id, principal))


@router.get("/{workflow_id}/versions")
async def list_versions(
    workflow_id: str, session: DbDep, principal: PrincipalDep
) -> list[dict[str, Any]]:
    await _require(session, workflow_id, principal)
    versions = await workflows_repo.list_versions(session, workflow_id)
    return [
        {"version": v.version, "verified": v.verified, "created_at": v.created_at.isoformat()}
        for v in versions
    ]


@router.get("/{workflow_id}/runs")
async def list_runs(
    workflow_id: str, session: DbDep, principal: PrincipalDep
) -> list[dict[str, Any]]:
    wf = await _require(session, workflow_id, principal)
    rows, _ = await exec_repo.list_executions(
        session, organization_id=principal.organization_id, workspace_id=wf.workspace_id, limit=50
    )
    return [
        {
            "execution_id": e.id,
            "status": e.status,
            "started_at": e.started_at.isoformat() if e.started_at else None,
        }
        for e in rows
    ]
