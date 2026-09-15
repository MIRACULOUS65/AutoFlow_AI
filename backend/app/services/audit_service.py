"""Audit service — append-oriented record of who did what, when, and the decision."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ActorType
from app.models.audit import AuditLog
from app.repositories import audit as audit_repo


async def record(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    actor: str | None = None,
    actor_type: ActorType = ActorType.USER,
    organization_id: str | None = None,
    workspace_id: str | None = None,
    decision: str | None = None,
    metadata: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor=actor,
        actor_type=actor_type.value,
        organization_id=organization_id,
        workspace_id=workspace_id,
        decision=decision,
        metadata_json=metadata or {},
        correlation_id=correlation_id,
    )
    return await audit_repo.add_audit(session, entry)
