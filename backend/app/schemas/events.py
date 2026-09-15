"""Execution event contract.

Every meaningful state transition emits a durable, sequenced event. Clients
reconnect via ?after=<sequence> and receive missing events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.domain.enums import ActorType, EventType
from app.schemas.common import Schema


class ExecutionEvent(Schema):
    id: str
    type: EventType
    organization_id: str | None = None
    workspace_id: str | None = None
    task_id: str | None = None
    execution_id: str | None = None
    step_id: str | None = None
    agent_run_id: str | None = None
    model_call_id: str | None = None
    tool_call_id: str | None = None
    verification_id: str | None = None
    sequence: int
    at: datetime
    actor_type: ActorType = ActorType.SYSTEM
    label: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
