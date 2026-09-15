"""Artifact contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.enums import ArtifactType, VerificationStatus
from app.schemas.common import Schema


class ArtifactSummary(Schema):
    id: str
    name: str
    kind: ArtifactType
    mime_type: str | None = None
    size_bytes: int = 0
    workspace_id: str
    execution_id: str | None = None
    task_id: str | None = None
    workflow_id: str | None = None
    verification_status: VerificationStatus | None = None
    content_hash: str | None = None
    created_by_agent: str | None = None
    created_at: datetime


class ArtifactDetail(ArtifactSummary):
    source_references: list[str] = Field(default_factory=list)
