from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, created_at_column, id_column, updated_at_column
from app.domain.enums import ApprovalStatus, RiskClass


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_ws_status", "workspace_id", "status"),)

    id: Mapped[str] = id_column("appr")
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_version: Mapped[int | None] = mapped_column(nullable=True)

    action_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    risk_class: Mapped[str] = mapped_column(
        String(16), default=RiskClass.MEDIUM.value, nullable=False
    )
    risk: Mapped[str | None] = mapped_column(String(400), nullable=True)
    plan_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target: Mapped[str | None] = mapped_column(String(400), nullable=True)
    attachment: Mapped[str | None] = mapped_column(String(400), nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), default=ApprovalStatus.PENDING.value, nullable=False
    )
    requested_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    requested_at: Mapped[datetime] = created_at_column()
    decision_timestamp: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = updated_at_column()


class ApprovalEvidence(Base):
    __tablename__ = "approval_evidence"

    id: Mapped[str] = id_column("ev")
    approval_id: Mapped[str] = mapped_column(
        ForeignKey("approvals.id"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(400), nullable=False)
    passed: Mapped[bool] = mapped_column(default=True, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
