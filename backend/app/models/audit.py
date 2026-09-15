from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, created_at_column, id_column


class AuditLog(Base):
    """Append-oriented audit record (PRD §56, §67)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_ws_ts", "workspace_id", "timestamp"),)

    id: Mapped[str] = id_column("audit")
    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), default="USER", nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = created_at_column()
