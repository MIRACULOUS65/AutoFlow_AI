"""The single authoritative execution/task state machine.

No service or route may mutate a status field directly. All transitions go
through `transition()` (or the named helpers), which validates legality and
rejects impossible transitions. Task and Execution share this lifecycle.

Legal transitions follow Backend PRD §21 and the master build prompt §21/§81.
"""

from __future__ import annotations

from app.core.errors import invalid_transition
from app.domain.enums import TaskStatus

# Adjacency map of allowed transitions.
_ALLOWED: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.QUEUED: frozenset({TaskStatus.PLANNING, TaskStatus.CANCELLED}),
    TaskStatus.PLANNING: frozenset(
        {TaskStatus.VALIDATING, TaskStatus.FAILED, TaskStatus.CANCELLED}
    ),
    TaskStatus.VALIDATING: frozenset(
        {
            TaskStatus.AWAITING_APPROVAL,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.AWAITING_APPROVAL: frozenset(
        {
            TaskStatus.RUNNING,
            TaskStatus.BLOCKED,
            TaskStatus.EXPIRED,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
        }
    ),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.VERIFYING,
            TaskStatus.RECOVERY,
            TaskStatus.AWAITING_APPROVAL,
            TaskStatus.CANCELLED,
            TaskStatus.FAILED,
            TaskStatus.COMPLETE,
        }
    ),
    TaskStatus.VERIFYING: frozenset(
        {
            TaskStatus.COMPLETE,
            TaskStatus.RUNNING,
            TaskStatus.RECOVERY,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }
    ),
    TaskStatus.RECOVERY: frozenset(
        {
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.CANCELLED,
        }
    ),
    # Terminal states — no outgoing transitions.
    TaskStatus.COMPLETE: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
    TaskStatus.EXPIRED: frozenset(),
    TaskStatus.BLOCKED: frozenset(
        {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.FAILED}
    ),
}


def is_terminal(state: TaskStatus) -> bool:
    return len(_ALLOWED.get(state, frozenset())) == 0 and state in {
        TaskStatus.COMPLETE,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.EXPIRED,
    }


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    if current == target:
        return False
    return target in _ALLOWED.get(current, frozenset())


def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    """Raise AppError(INVALID_STATE_TRANSITION) if the move is illegal."""
    if not can_transition(current, target):
        raise invalid_transition(current.value, target.value)


def transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    """Return the validated target state (pure — callers persist the result)."""
    validate_transition(current, target)
    return target


def allowed_from(current: TaskStatus) -> frozenset[TaskStatus]:
    return _ALLOWED.get(current, frozenset())
