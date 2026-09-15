from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonB, created_at_column, id_column
from app.domain.enums import AgentStatus


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # stable id, e.g. agent_spreadsheet
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), default="planner", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    capabilities: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    supported_tools: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    tools: Mapped[list] = mapped_column(JsonB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=AgentStatus.AVAILABLE.value, nullable=False
    )
    version: Mapped[str] = mapped_column(String(16), default="1.0", nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id: Mapped[str] = id_column("agentver")
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_column()
