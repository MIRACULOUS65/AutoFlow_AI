"""Shared schema primitives: base model config, pagination, error envelope."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Schema(BaseModel):
    """Base for all API schemas. Reads from ORM attributes."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Page(Schema, Generic[T]):
    items: list[T]
    page: int = 1
    page_size: int = 50
    total: int = 0
    next_cursor: str | None = None


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class ErrorBody(Schema):
    code: str
    message: str
    request_id: str | None = None
    details: dict | None = None


class ErrorEnvelope(Schema):
    error: ErrorBody


class Ack(Schema):
    """Generic acknowledgement for command endpoints."""

    ok: bool = True
    message: str | None = None


class TimestampMixin(Schema):
    created_at: datetime
    updated_at: datetime | None = None
