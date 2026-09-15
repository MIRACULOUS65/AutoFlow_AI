"""Event repository. Events are durable and per-execution monotonically sequenced."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event


async def add_event(session: AsyncSession, event: Event) -> Event:
    session.add(event)
    await session.flush()
    return event


async def list_events_after(
    session: AsyncSession,
    execution_id: str,
    *,
    after: int = 0,
    limit: int = 500,
) -> Sequence[Event]:
    res = await session.execute(
        select(Event)
        .where(Event.execution_id == execution_id, Event.sequence > after)
        .order_by(Event.sequence)
        .limit(limit)
    )
    return res.scalars().all()


async def list_events_for_task(
    session: AsyncSession, task_id: str, *, after: int = 0
) -> Sequence[Event]:
    res = await session.execute(
        select(Event)
        .where(Event.task_id == task_id, Event.sequence > after)
        .order_by(Event.sequence)
    )
    return res.scalars().all()


async def latest_sequence(session: AsyncSession, execution_id: str) -> int:
    res = await session.execute(
        select(Event.sequence)
        .where(Event.execution_id == execution_id)
        .order_by(Event.sequence.desc())
        .limit(1)
    )
    return int(res.scalar_one_or_none() or 0)
