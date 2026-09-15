from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_column, id_column


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (Index("ix_artifacts_exec", "execution_id"),)

    id: Mapped[str] = id_column("art")
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    size_bytes: Mapped[int] = mapped_column(default=0, nullable=False)

    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    content_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(600), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_by_agent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class ArtifactSource(Base):
    __tablename__ = "artifact_sources"

    id: Mapped[str] = id_column("artsrc")
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False, index=True
    )
    reference: Mapped[str] = mapped_column(String(600), nullable=False)
