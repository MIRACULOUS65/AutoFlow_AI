"""Workspace + organization schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import Schema


class OrganizationOut(Schema):
    id: str
    name: str
    status: str
    created_at: datetime


class WorkspaceOut(Schema):
    id: str
    organization_id: str
    name: str
    slug: str | None = None
    description: str | None = None
    policy_profile: str = "standard"
    capabilities: list[str] = Field(default_factory=list)
    members: int = 0
    created_at: datetime


class WorkspaceCreate(Schema):
    name: str
    policy_profile: str = "standard"
    capabilities: list[str] = Field(default_factory=list)
