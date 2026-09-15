from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    JsonB,
    created_at_column,
    id_column,
    updated_at_column,
)
from app.domain.enums import TaskStatus


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (
        Index("ix_exec_task_created", "task_id", "created_at"),
        Index("ix_exec_ws_status", "workspace_id", "status"),
    )

    id: Mapped[str] = id_column("exec")
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_version: Mapped[int] = mapped_column(default=0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), default=TaskStatus.QUEUED.value, nullable=False
    )
    current_step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    verification_status: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Optimistic concurrency version (PRD §51).
    version: Mapped[int] = mapped_column(default=0, nullable=False)

    budget: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    last_sequence: Mapped[int] = mapped_column(default=0, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class ExecutionContextSnapshotModel(Base):
    __tablename__ = "execution_context_snapshots"

    id: Mapped[str] = id_column("ctx")
    execution_id: Mapped[str] = mapped_column(
        ForeignKey("executions.id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    permissions: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    policy_profile: Mapped[str] = mapped_column(String(64), default="standard")
    tool_allowlist: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    context_namespace: Mapped[str] = mapped_column(String(120), nullable=False)
    budget: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
