"""Artifact service — persists artifacts produced by tool executions."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ActorType, ArtifactType, EventType, VerificationStatus
from app.models.artifact import Artifact
from app.repositories import artifacts as artifacts_repo
from app.services import event_service
from app.services.artifact_store import get_artifact_store

_EXT_TO_KIND = {
    "xlsx": ArtifactType.XLSX,
    "docx": ArtifactType.DOCX,
    "pptx": ArtifactType.PPTX,
    "pdf": ArtifactType.PDF,
    "csv": ArtifactType.CSV,
    "json": ArtifactType.JSON,
}


def _kind_for(name: str) -> ArtifactType:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _EXT_TO_KIND.get(ext, ArtifactType.JSON)


async def create_from_tool(
    session: AsyncSession,
    *,
    name: str,
    execution_id: str,
    task_id: str,
    organization_id: str,
    workspace_id: str,
    created_by_agent: str | None,
    body: bytes | None = None,
) -> Artifact:
    store = get_artifact_store()
    data = body if body is not None else f"mock artifact: {name}".encode()
    storage_path, digest = await store.put(name, data)

    artifact = Artifact(
        name=name,
        kind=_kind_for(name).value,
        size_bytes=len(data),
        organization_id=organization_id,
        workspace_id=workspace_id,
        execution_id=execution_id,
        task_id=task_id,
        content_hash=digest,
        storage_path=storage_path,
        verification_status=VerificationStatus.PENDING.value,
        created_by_agent=created_by_agent,
    )
    await artifacts_repo.add_artifact(session, artifact)

    await event_service.emit(
        session,
        type=EventType.ARTIFACT_CREATED,
        execution_id=execution_id,
        task_id=task_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        actor_type=ActorType.AGENT,
        label=f"Artifact created: {name}",
        payload={"artifact_id": artifact.id, "name": name},
    )
    return artifact
