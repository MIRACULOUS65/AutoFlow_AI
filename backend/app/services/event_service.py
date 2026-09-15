"""Event service — the single way to emit durable, sequenced events.

Every meaningful state transition emits an event via `emit`. The sequence is
allocated atomically per execution so clients can reconnect with ?after=<seq>.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ActorType, EventType
from app.models.event import Event
from app.repositories import events as events_repo
from app.repositories import executions as exec_repo


async def emit(
    session: AsyncSession,
    *,
    type: EventType,
    execution_id: str | None = None,
    task_id: str | None = None,
    organization_id: str | None = None,
    workspace_id: str | None = None,
    step_id: str | None = None,
    agent_run_id: str | None = None,
    tool_call_id: str | None = None,
    verification_id: str | None = None,
    actor_type: ActorType = ActorType.SYSTEM,
    label: str | None = None,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> Event:
    sequence = 0
    if execution_id:
        sequence = await exec_repo.allocate_event_sequence(session, execution_id)

    event = Event(
        type=type.value,
        execution_id=execution_id,
        task_id=task_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        step_id=step_id,
        agent_run_id=agent_run_id,
        tool_call_id=tool_call_id,
        verification_id=verification_id,
        sequence=sequence,
        actor_type=actor_type.value,
        label=label,
        payload=payload or {},
        trace_id=trace_id,
    )
    return await events_repo.add_event(session, event)
