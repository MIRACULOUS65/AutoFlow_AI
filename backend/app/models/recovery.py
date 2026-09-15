from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, created_at_column, id_column


class RecoveryRun(Base):
    __tablename__ = "recovery_runs"

    id: Mapped[str] = id_column("rec")
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt: Mapped[int] = mapped_column(default=1, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
