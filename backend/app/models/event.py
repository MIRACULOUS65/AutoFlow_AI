from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, id_column
from app.db.base import created_at_column


class Event(Base):
    """Durable, monotonically-sequenced execution event (PRD §25–27)."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("execution_id", "sequence", name="uq_event_exec_seq"),
        Index("ix_events_exec_seq", "execution_id", "sequence"),
    )

    id: Mapped[str] = id_column("evt")
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    sequence: Mapped[int] = mapped_column(nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), default="SYSTEM", nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = created_at_column()
