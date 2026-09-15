"""AgentMessage protocol + MessageBus (real agent-to-agent communication).

Agents exchange typed, structured messages — not log comments. The bus records
an ordered, serializable trace, enforces a message budget, and detects
message loops (A->B->A->B or repeated identical messages) so agents can't chatter
forever.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ..schemas.common import AutoFlowModel, utcnow
from ..schemas.enums import StrEnum


class MessageType(StrEnum):
    TASK_REQUEST = "task_request"
    TASK_ACCEPTED = "task_accepted"
    STATUS_UPDATE = "status_update"
    ACTION_REQUEST = "action_request"
    RESULT = "result"
    HANDOFF = "handoff"
    BLOCKED = "blocked"
    NEEDS_CONTEXT = "needs_context"
    NEEDS_APPROVAL = "needs_approval"
    VERIFICATION_REQUEST = "verification_request"
    VERIFICATION_RESULT = "verification_result"
    FAILURE = "failure"
    REPLAN_REQUEST = "replan_request"
    COMPLETED = "completed"
    CANCEL = "cancel"


class AgentMessage(AutoFlowModel):
    message_id: str = Field(min_length=1, max_length=64)
    execution_id: str
    sender: str
    recipient: str
    type: MessageType
    task_id: str | None = None
    objective: str = ""
    summary: str = Field(default="", max_length=1024)
    evidence_refs: tuple[str, ...] = ()
    input_refs: tuple[str, ...] = ()
    output_refs: tuple[str, ...] = ()
    requested_capability: str | None = None
    payload: dict = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    priority: int = Field(default=5, ge=0, le=10)
    timestamp: datetime = Field(default_factory=utcnow)

    def loop_key(self) -> str:
        return f"{self.sender}->{self.recipient}:{self.type}:{self.task_id}"


class MessageBus:
    """Ordered, budgeted message bus with loop detection."""

    def __init__(self, *, max_messages: int = 200, max_repeat: int = 4) -> None:
        self._max = max_messages
        self._max_repeat = max_repeat
        self._log: list[AgentMessage] = []
        self._queues: dict[str, list[AgentMessage]] = {}
        self._loop_counts: dict[str, int] = {}
        self.overflow = False
        self.loop_detected = False

    @property
    def messages(self) -> list[AgentMessage]:
        return list(self._log)

    def send(self, msg: AgentMessage) -> bool:
        """Return True if delivered; False if budget/loop blocked it."""

        if len(self._log) >= self._max:
            self.overflow = True
            return False
        key = msg.loop_key()
        self._loop_counts[key] = self._loop_counts.get(key, 0) + 1
        if self._loop_counts[key] > self._max_repeat:
            self.loop_detected = True
            return False
        self._log.append(msg)
        self._queues.setdefault(msg.recipient, []).append(msg)
        return True

    def receive(self, recipient: str) -> list[AgentMessage]:
        msgs = self._queues.get(recipient, [])
        self._queues[recipient] = []
        return msgs

    def trace(self) -> list[dict]:
        return [
            {
                "from": m.sender,
                "to": m.recipient,
                "type": str(m.type),
                "task": m.task_id,
                "summary": m.summary[:120],
            }
            for m in self._log
        ]
