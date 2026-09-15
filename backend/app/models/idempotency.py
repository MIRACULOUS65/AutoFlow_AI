from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, created_at_column, id_column


class IdempotencyKey(Base):
    """Stored idempotency records (PRD §21, API §23)."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("principal_id", "route", "idempotency_key", name="uq_idem"),
    )

    id: Mapped[str] = id_column("idem")
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    response: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    created_at: Mapped[datetime] = created_at_column()
