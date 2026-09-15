"""Idempotency key repository (PRD §21, API §23)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idempotency import IdempotencyKey


async def get_key(
    session: AsyncSession, *, principal_id: str, route: str, key: str
) -> IdempotencyKey | None:
    res = await session.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.principal_id == principal_id,
            IdempotencyKey.route == route,
            IdempotencyKey.idempotency_key == key,
        )
    )
    return res.scalar_one_or_none()


async def store_key(
    session: AsyncSession,
    *,
    principal_id: str,
    route: str,
    key: str,
    request_hash: str,
    response: dict,
) -> IdempotencyKey:
    record = IdempotencyKey(
        principal_id=principal_id,
        route=route,
        idempotency_key=key,
        request_hash=request_hash,
        response=response,
        status="COMPLETED",
    )
    session.add(record)
    await session.flush()
    return record
