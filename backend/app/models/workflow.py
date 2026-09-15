from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, created_at_column, id_column, updated_at_column


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = id_column("wf")
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current_version: Mapped[str] = mapped_column(String(16), default="v1", nullable=False)
    runs: Mapped[int] = mapped_column(default=0, nullable=False)
    success_rate: Mapped[int] = mapped_column(default=100, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    agent_ids: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    step_titles: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    artifact_ids: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    id: Mapped[str] = id_column("wfv")
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    graph: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
