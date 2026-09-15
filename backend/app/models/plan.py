from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, created_at_column, id_column
from app.domain.enums import PlanValidationStatus, RiskClass, StepStatus


class TaskPlan(Base):
    __tablename__ = "task_plans"
    __table_args__ = (
        UniqueConstraint("task_id", "version", name="uq_plan_task_version"),
        Index("ix_plans_task", "task_id"),
    )

    id: Mapped[str] = id_column("plan")
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    generated_by: Mapped[str] = mapped_column(String(64), default="orchestrator")
    validation_status: Mapped[str] = mapped_column(
        String(16), default=PlanValidationStatus.DRAFT.value, nullable=False
    )
    risk_summary: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    required_approvals: Mapped[int] = mapped_column(default=0, nullable=False)
    plan_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    graph: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class TaskStep(Base):
    """Persisted step definition + live state for a plan version."""

    __tablename__ = "task_steps"
    __table_args__ = (Index("ix_steps_plan", "plan_id"),)

    id: Mapped[str] = id_column("step")
    plan_id: Mapped[str] = mapped_column(ForeignKey("task_plans.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    index: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    agent_profile: Mapped[str] = mapped_column(String(64), nullable=False)
    dependencies: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    allowed_tools: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    inputs: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    expected_state: Mapped[str] = mapped_column(Text, nullable=False)
    preconditions: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    verification_checks: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    risk_class: Mapped[str] = mapped_column(
        String(16), default=RiskClass.LOW.value, nullable=False
    )
    timeout_seconds: Mapped[int] = mapped_column(default=300, nullable=False)
    retry_policy: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    recovery_budget: Mapped[int] = mapped_column(default=3, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Live state
    status: Mapped[str] = mapped_column(
        String(16), default=StepStatus.WAITING.value, nullable=False
    )
    verification_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    current_state: Mapped[str] = mapped_column(Text, default="", nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
