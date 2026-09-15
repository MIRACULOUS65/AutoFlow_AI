"""Artifact endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.api.deps import DbDep, PrincipalDep
from app.api.serializers import artifact_summary
from app.core.errors import not_found
from app.repositories import artifacts as artifacts_repo
from app.schemas.artifacts import ArtifactSummary
from app.schemas.common import Page
from app.services.artifact_store import get_artifact_store

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("", response_model=Page[ArtifactSummary])
async def list_artifacts(
    session: DbDep,
    principal: PrincipalDep,
    workspace_id: str | None = None,
    kind: str | None = None,
    task_id: str | None = None,
    execution_id: str | None = None,
    verification_status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[ArtifactSummary]:
    rows, total = await artifacts_repo.list_artifacts(
        session,
        organization_id=principal.organization_id,
        workspace_id=workspace_id,
        kind=kind,
        task_id=task_id,
        execution_id=execution_id,
        verification_status=verification_status,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page[ArtifactSummary](
        items=[artifact_summary(a) for a in rows], page=page, page_size=page_size, total=total
    )


async def _load(session, artifact_id: str, principal):
    art = await artifacts_repo.get_artifact(
        session, artifact_id, organization_id=principal.organization_id
    )
    if art is None:
        raise not_found("Artifact", artifact_id)
    return art


@router.get("/{artifact_id}", response_model=ArtifactSummary)
async def get_artifact(
    artifact_id: str, session: DbDep, principal: PrincipalDep
) -> ArtifactSummary:
    art = await _load(session, artifact_id, principal)
    return artifact_summary(art)


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: str, session: DbDep, principal: PrincipalDep
) -> Response:
    art = await _load(session, artifact_id, principal)
    data = b""
    if art.storage_path:
        try:
            data = await get_artifact_store().get(art.storage_path)
        except FileNotFoundError:
            data = b""
    return Response(
        content=data,
        media_type=art.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{art.name}"'},
    )
