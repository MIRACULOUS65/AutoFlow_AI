from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, created_at_column, id_column
from app.domain.enums import VerificationStatus


class VerificationRun(Base):
    __tablename__ = "verification_runs"

    id: Mapped[str] = id_column("ver")
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default=VerificationStatus.PENDING.value, nullable=False
    )
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    evidence: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class VerificationCheckModel(Base):
    __tablename__ = "verification_checks"

    id: Mapped[str] = id_column("vchk")
    verification_run_id: Mapped[str] = mapped_column(
        ForeignKey("verification_runs.id"), nullable=False, index=True
    )
    check_id: Mapped[str] = mapped_column(String(120), nullable=False)
    passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
