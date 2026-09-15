from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    JsonB,
    created_at_column,
    id_column,
    updated_at_column,
)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = id_column("ws")
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    policy_profile: Mapped[str] = mapped_column(
        String(64), default="standard", nullable=False
    )
    capabilities: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    members: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
