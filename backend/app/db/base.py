"""Declarative base + shared column helpers.

Uses UUID string ids (UUIDv7-like ordering via time-sortable generation) and
UTC timestamps. JSONB is used on PostgreSQL and falls back to JSON on SQLite so
the same models run on both.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Shared declarative base."""


# JSON that is JSONB on Postgres and JSON elsewhere (SQLite).
JsonB = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Time-sortable, prefixed identifier, e.g. task_017f3a...."""
    return f"{prefix}_{uuid.uuid4().hex}"


def id_column(prefix: str) -> Mapped[str]:
    return mapped_column(
        String(64),
        primary_key=True,
        default=lambda: new_id(prefix),
    )


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def updated_at_column() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
