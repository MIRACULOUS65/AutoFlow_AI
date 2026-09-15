"""Autonomy support: recovery ladder, stuck detection, approval binding,
rate limits, and resource locks (CP4 + CP5).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field

from ..schemas.enums import StrEnum


# ---------------------------------------------------------------------------
# recovery + stuck detection (CP4)
# ---------------------------------------------------------------------------


class RecoveryStep(StrEnum):
    RETRY = "retry"
    RE_OBSERVE = "re_observe"
    RE_RESOLVE = "re_resolve"
    ALTERNATE_METHOD = "alternate_method"
    SWITCH_SOURCE = "switch_source"
    VISION = "vision"
    REPLAN = "replan"
    HUMAN = "human"
    FAIL_SAFE = "fail_safe"


# ordered ladder
RECOVERY_LADDER: tuple[RecoveryStep, ...] = (
    RecoveryStep.RETRY,
    RecoveryStep.RE_OBSERVE,
    RecoveryStep.RE_RESOLVE,
    RecoveryStep.ALTERNATE_METHOD,
    RecoveryStep.SWITCH_SOURCE,
    RecoveryStep.VISION,
    RecoveryStep.REPLAN,
    RecoveryStep.HUMAN,
    RecoveryStep.FAIL_SAFE,
)


@dataclass
class RecoveryEngine:
    """Advances through the bounded recovery ladder. Preserves completed work:
    the caller only replans the failed node + downstream, never verified nodes."""

    max_steps: int = 5
    _index: int = 0
    _attempts: int = 0

    def next_step(self) -> RecoveryStep:
        if self._attempts >= self.max_steps:
            return RecoveryStep.FAIL_SAFE
        step = RECOVERY_LADDER[min(self._index, len(RECOVERY_LADDER) - 1)]
        self._index += 1
        self._attempts += 1
        return step

    @property
    def exhausted(self) -> bool:
        return self._attempts >= self.max_steps


@dataclass
class StuckDetector:
    """Detects loops: repeated state hashes, repeated actions, no postcondition
    change. Returns True when progress has stalled."""

    max_same_state: int = 3
    max_same_action: int = 3
    _state_counts: dict[str, int] = field(default_factory=dict)
    _action_counts: dict[str, int] = field(default_factory=dict)

    def record_state(self, state_hash: str) -> bool:
        self._state_counts[state_hash] = self._state_counts.get(state_hash, 0) + 1
        return self._state_counts[state_hash] >= self.max_same_state

    def record_action(self, action_key: str) -> bool:
        self._action_counts[action_key] = self._action_counts.get(action_key, 0) + 1
        return self._action_counts[action_key] >= self.max_same_action


# ---------------------------------------------------------------------------
# approval binding (CP5)
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequest:
    execution_id: str
    task_id: str
    action_id: str
    tool: str
    risk: str
    target: dict
    arguments: dict
    observation_hash: str

    def binding_hash(self) -> str:
        payload = {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "action_id": self.action_id,
            "tool": self.tool,
            "target": self.target,
            "arguments": self.arguments,
            "observation_hash": self.observation_hash,
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ApprovalLedger:
    """Records granted approvals bound to an exact action/observation hash.

    An approval is only valid for the exact action+args+observation it was
    granted for; any material change invalidates it (must re-request).
    """

    def __init__(self) -> None:
        self._granted: set[str] = set()

    def grant(self, request: ApprovalRequest) -> str:
        h = request.binding_hash()
        self._granted.add(h)
        return h

    def is_approved(self, request: ApprovalRequest) -> bool:
        return request.binding_hash() in self._granted


# ---------------------------------------------------------------------------
# rate limits (CP5)
# ---------------------------------------------------------------------------


@dataclass
class RateLimits:
    max_actions_per_task: int = 40
    max_actions_per_minute: int = 120
    max_replans: int = 2
    max_runtime_seconds: float = 300.0

    _actions: int = 0
    _replans: int = 0
    _timestamps: list[float] = field(default_factory=list)
    _start: float = field(default_factory=time.time)

    def allow_action(self) -> tuple[bool, str]:
        if self._actions >= self.max_actions_per_task:
            return False, "max_actions_per_task reached"
        now = time.time()
        if now - self._start > self.max_runtime_seconds:
            return False, "max_runtime_seconds reached"
        self._timestamps = [t for t in self._timestamps if now - t < 60]
        if len(self._timestamps) >= self.max_actions_per_minute:
            return False, "max_actions_per_minute reached"
        return True, ""

    def record_action(self) -> None:
        self._actions += 1
        self._timestamps.append(time.time())

    def allow_replan(self) -> bool:
        return self._replans < self.max_replans

    def record_replan(self) -> None:
        self._replans += 1

    @property
    def action_count(self) -> int:
        return self._actions


# ---------------------------------------------------------------------------
# resource locks (CP5)
# ---------------------------------------------------------------------------


class ResourceLocks:
    """Serializes GUI-mutating actions against the same resource.

    Never run two mutations against the same application/window/file/browser
    context concurrently. Independent resources may proceed in parallel.
    """

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def lock_for(self, resource_key: str) -> threading.Lock:
        with self._guard:
            if resource_key not in self._locks:
                self._locks[resource_key] = threading.Lock()
            return self._locks[resource_key]
