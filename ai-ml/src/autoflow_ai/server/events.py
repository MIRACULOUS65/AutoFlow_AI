"""One canonical mission event contract, shared by CLI / API / frontend.

Every event is a small, secret-safe dict. The same events feed the CLI live
trace, the API SSE stream, and the frontend timeline — a single contract, not
three event systems.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..schemas.enums import StrEnum


class EventType(StrEnum):
    MISSION_STARTED = "mission_started"
    CONTEXT_BUILT = "context_built"
    EVIDENCE_RETRIEVED = "evidence_retrieved"
    PLAN_CREATED = "plan_created"
    TASK_DELEGATED = "task_delegated"
    ACTION_PROPOSED = "action_proposed"
    TOOL_COMPLETED = "tool_completed"
    OBSERVATION_CAPTURED = "observation_captured"
    VERIFICATION_PASSED = "verification_passed"
    VERIFICATION_FAILED = "verification_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    RECOVERY_STARTED = "recovery_started"
    ARTIFACT_CREATED = "artifact_created"
    CLEANUP_COMPLETED = "cleanup_completed"
    MISSION_COMPLETED = "mission_completed"
    MISSION_FAILED = "mission_failed"
    STAGE = "stage"                      # generic stage/trace line


_SECRETS = ("api_key", "authorization", "bearer", "token", "password", "secret",
            "cookie", "nvapi-", "ms-cfaabe", "sk-")


def _clean(text: str) -> str:
    low = (text or "").lower()
    for s in _SECRETS:
        if s in low:
            return "[redacted]"
    return (text or "")[:400]


@dataclass
class MissionEvent:
    mission_id: str
    type: EventType
    source: str = "system"
    status: str = "info"                 # info | ok | fail | waiting
    message: str = ""
    payload: dict = field(default_factory=dict)
    event_id: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "event_id": self.event_id,
            "type": str(self.type),
            "source": self.source,
            "status": self.status,
            "message": _clean(self.message),
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    def sse(self) -> str:
        import json

        return f"event: {self.type}\ndata: {json.dumps(self.as_dict())}\n\n"


class MissionEventBus:
    """Thread-safe append-only event log per mission + simple subscription."""

    def __init__(self) -> None:
        self._events: list[MissionEvent] = []
        self._lock = threading.Lock()
        self._seq = 0
        self._closed = False

    def emit(self, mission_id: str, etype: EventType, *, source="system",
             status="info", message="", payload=None) -> MissionEvent:
        with self._lock:
            self._seq += 1
            ev = MissionEvent(mission_id=mission_id, type=etype, source=source,
                              status=status, message=message, payload=payload or {},
                              event_id=self._seq)
            self._events.append(ev)
            return ev

    def since(self, after_id: int = 0) -> list[MissionEvent]:
        with self._lock:
            return [e for e in self._events if e.event_id > after_id]

    def all(self) -> list[MissionEvent]:
        with self._lock:
            return list(self._events)

    def close(self) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed
