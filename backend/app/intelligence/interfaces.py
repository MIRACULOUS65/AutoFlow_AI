"""The IntelligenceRuntime contract.

This is the coarse "mission" boundary (audit §9, Level A): the control plane
asks the intelligence layer to produce a plan and to run a mission, and it
receives back plans, a stream of operational events, and a verified outcome.
The control plane remains authoritative for identity, state, approval, event
sequencing and audit; the intelligence layer is authoritative for plan content,
agent reasoning, real tool execution and verification.

Both the mock runtime and the real AI/ML runtime implement this interface, so
`app/runtime.py` can flip between them with zero changes elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.schemas.plan import Plan


@dataclass
class PlanResult:
    """A plan produced by the intelligence layer, already mapped to the CP Plan
    contract, plus any intelligence-native correlation ids."""

    plan: Plan
    external_ref: str | None = None  # e.g. AI/ML mission id
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntelligenceEvent:
    """A control-plane-canonical event emitted by the intelligence layer.

    `type` is a CP EventType value (dotted, e.g. "verification.passed"); the
    adapter has already translated the AI/ML event vocabulary.
    """

    type: str
    label: str
    status: str = "info"  # info | ok | fail | waiting
    step_ref: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionOutcome:
    """Terminal result of running a mission.

    `verified` is the honest verification truth (never model confidence). The
    control plane maps this to a VerificationResult and gates COMPLETE on it.
    """

    status: str  # CP terminal-ish status: COMPLETE | FAILED | AWAITING_APPROVAL | BLOCKED
    verified: bool
    outcome: str  # intelligence-native outcome string (for audit/detail)
    reason: str | None = None
    external_ref: str | None = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    events: list[IntelligenceEvent] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionRequest:
    """What the control plane hands the intelligence layer to run a mission."""

    task_id: str
    execution_id: str
    workspace_id: str
    organization_id: str
    goal: str
    target_path: str | None = None
    use_model: bool = False
    constraints: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


class IntelligenceRuntime(Protocol):
    async def available(self) -> bool:
        """Cheap health probe; False when the runtime cannot be reached."""
        ...

    async def create_plan(self, request: MissionRequest) -> PlanResult:
        """Produce a validated-by-intelligence plan mapped to the CP Plan shape."""
        ...

    async def run_mission(self, request: MissionRequest) -> MissionOutcome:
        """Execute the mission and return a verified outcome + translated events."""
        ...
