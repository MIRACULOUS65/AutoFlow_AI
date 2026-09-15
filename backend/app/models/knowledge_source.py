from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_column, id_column, updated_at_column


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = id_column("kn")
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="guide", nullable=False)
    access: Mapped[str] = mapped_column(String(32), default="workspace", nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    provenance: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    size_bytes: Mapped[int] = mapped_column(default=0, nullable=False)
    updated_at: Mapped[datetime] = updated_at_column()
    created_at: Mapped[datetime] = created_at_column()
