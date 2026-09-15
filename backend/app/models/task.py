from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    JsonB,
    created_at_column,
    id_column,
    updated_at_column,
)
from app.domain.enums import TaskStatus


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_ws_created", "workspace_id", "created_at"),
        Index("ix_tasks_ws_status", "workspace_id", "status"),
    )

    id: Mapped[str] = id_column("task")
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    client_metadata: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    priority: Mapped[int] = mapped_column(default=0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), default=TaskStatus.QUEUED.value, nullable=False
    )
    current_plan_version: Mapped[int] = mapped_column(default=0, nullable=False)
    current_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(16), nullable=True)

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id: Mapped[str] = id_column("att")
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(400), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    size: Mapped[int | None] = mapped_column(nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_at_column()
