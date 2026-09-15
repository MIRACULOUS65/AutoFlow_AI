"""Knowledge source endpoints (metadata only; authorization != retrieval)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import DbDep, PrincipalDep
from app.core.errors import not_found
from app.repositories import knowledge as knowledge_repo
from app.schemas.common import Page, Schema

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeSourceOut(Schema):
    id: str
    workspace_id: str
    title: str
    type: str
    access: str
    version: str
    provenance: str
    summary: str
    size_bytes: int
    updated_at: datetime


def _out(k) -> KnowledgeSourceOut:
    return KnowledgeSourceOut(
        id=k.id,
        workspace_id=k.workspace_id,
        title=k.title,
        type=k.type,
        access=k.access,
        version=k.version,
        provenance=k.provenance,
        summary=k.summary,
        size_bytes=k.size_bytes,
        updated_at=k.updated_at,
    )


@router.get("/sources", response_model=Page[KnowledgeSourceOut])
async def list_sources(
    session: DbDep,
    principal: PrincipalDep,
    workspace_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[KnowledgeSourceOut]:
    rows, total = await knowledge_repo.list_sources(
        session,
        organization_id=principal.organization_id,
        workspace_id=workspace_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page[KnowledgeSourceOut](
        items=[_out(k) for k in rows], page=page, page_size=page_size, total=total
    )


@router.get("/sources/{source_id}", response_model=KnowledgeSourceOut)
async def get_source(
    source_id: str, session: DbDep, principal: PrincipalDep
) -> KnowledgeSourceOut:
    src = await knowledge_repo.get_source(
        session, source_id, organization_id=principal.organization_id
    )
    if src is None:
        raise not_found("Knowledge source", source_id)
    return _out(src)
