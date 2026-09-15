"""Execution, observation, verification and recovery contracts."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .common import (
    IdStr,
    Reference,
    VersionedModel,
    validate_id,
)
from .enums import (
    ExecutionStatus,
    RecoveryStrategy,
    StepStatus,
    VerificationKind,
    VerificationStatus,
)


class Observation(VersionedModel):
    """Captured post-action state used for verification (FR-09)."""

    observation_id: IdStr
    execution_id: IdStr
    step_id: IdStr
    summary: str = Field(min_length=1, max_length=2000)
    data: dict = Field(default_factory=dict)
    evidence: tuple[Reference, ...] = ()

    @field_validator("observation_id")
    @classmethod
    def _oid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="obs")

    @field_validator("execution_id")
    @classmethod
    def _eid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="exec")

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")


class VerificationCheck(VersionedModel):
    """A single postcondition check within a verification result."""

    check_id: str = Field(min_length=1, max_length=64)
    kind: VerificationKind
    passed: bool
    detail: str | None = Field(default=None, max_length=1024)


class VerificationResult(VersionedModel):
    """Outcome of verifying a step. Material steps cannot pass on tool
    success alone (FR-10)."""

    verification_id: IdStr
    execution_id: IdStr
    step_id: IdStr
    status: VerificationStatus
    checks: tuple[VerificationCheck, ...] = ()
    evidence: tuple[Reference, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("verification_id")
    @classmethod
    def _vid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="ver")

    @field_validator("execution_id")
    @classmethod
    def _eid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="exec")

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")

    @model_validator(mode="after")
    def _status_matches_checks(self) -> "VerificationResult":
        if self.status == VerificationStatus.PASSED:
            if not self.checks:
                raise ValueError("passed verification must contain at least one check")
            if any(not c.passed for c in self.checks):
                raise ValueError("passed verification cannot contain a failed check")
        if self.status == VerificationStatus.FAILED and self.checks:
            if all(c.passed for c in self.checks):
                raise ValueError("failed verification cannot have all checks passing")
        return self


class RecoveryDecision(VersionedModel):
    """A bounded recovery decision (FR-11, EXECUTION_RUNTIME §10)."""

    decision_id: IdStr
    execution_id: IdStr
    step_id: IdStr
    strategy: RecoveryStrategy
    attempt_number: int = Field(ge=1)
    failure_type: str = Field(min_length=1, max_length=128)
    remaining_attempts: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1024)

    @field_validator("decision_id")
    @classmethod
    def _did(cls, v: str) -> str:
        return validate_id(v, expected_prefix="rec")

    @field_validator("execution_id")
    @classmethod
    def _eid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="exec")

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")


class ExecutionBudget(VersionedModel):
    """Hard limits that bound autonomy (master prompt §21, RULE 12/18)."""

    max_tool_calls: int = Field(default=50, ge=1)
    max_model_calls: int = Field(default=50, ge=1)
    max_replans: int = Field(default=3, ge=0)
    max_recovery_attempts: int = Field(default=5, ge=0)
    max_runtime_seconds: float = Field(default=3600.0, gt=0)


class ExecutionStep(VersionedModel):
    """Runtime state of one step within an execution."""

    step_id: IdStr
    status: StepStatus = StepStatus.PENDING
    attempts: int = Field(default=0, ge=0)
    last_observation: Reference | None = None
    last_verification: Reference | None = None

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")


class Execution(VersionedModel):
    """A durable, stateful execution of a plan version.

    State transitions are validated against :func:`is_valid_transition` when
    used with ``transition_to``.
    """

    execution_id: IdStr
    task_id: IdStr
    plan_version: int = Field(ge=1)
    status: ExecutionStatus = ExecutionStatus.QUEUED
    steps: tuple[ExecutionStep, ...] = ()
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)

    @field_validator("execution_id")
    @classmethod
    def _eid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="exec")

    @field_validator("task_id")
    @classmethod
    def _tid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="task")

    @property
    def is_terminal(self) -> bool:
        from .enums import TERMINAL_EXECUTION_STATES

        return self.status in TERMINAL_EXECUTION_STATES


# Allowed transitions in the execution state machine (EXECUTION_RUNTIME §3).
_ALLOWED_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.QUEUED: frozenset({ExecutionStatus.PLANNING, ExecutionStatus.CANCELLED}),
    ExecutionStatus.PLANNING: frozenset(
        {ExecutionStatus.VALIDATING, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED}
    ),
    ExecutionStatus.VALIDATING: frozenset(
        {
            ExecutionStatus.AWAITING_APPROVAL,
            ExecutionStatus.RUNNING,
            ExecutionStatus.FAILED,
            ExecutionStatus.BLOCKED,
            ExecutionStatus.CANCELLED,
        }
    ),
    ExecutionStatus.AWAITING_APPROVAL: frozenset(
        {
            ExecutionStatus.RUNNING,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.EXPIRED,
            ExecutionStatus.BLOCKED,
        }
    ),
    ExecutionStatus.RUNNING: frozenset(
        {
            ExecutionStatus.VERIFYING,
            ExecutionStatus.AWAITING_APPROVAL,
            ExecutionStatus.RECOVERY,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.FAILED,
        }
    ),
    ExecutionStatus.VERIFYING: frozenset(
        {
            ExecutionStatus.RUNNING,
            ExecutionStatus.RECOVERY,
            ExecutionStatus.COMPLETE,
            ExecutionStatus.FAILED,
        }
    ),
    ExecutionStatus.RECOVERY: frozenset(
        {
            ExecutionStatus.RUNNING,
            ExecutionStatus.VALIDATING,
            ExecutionStatus.AWAITING_APPROVAL,
            ExecutionStatus.FAILED,
            ExecutionStatus.BLOCKED,
            ExecutionStatus.CANCELLED,
        }
    ),
    # Terminal states have no outgoing transitions.
    ExecutionStatus.COMPLETE: frozenset(),
    ExecutionStatus.FAILED: frozenset(),
    ExecutionStatus.CANCELLED: frozenset(),
    ExecutionStatus.EXPIRED: frozenset(),
    ExecutionStatus.BLOCKED: frozenset(),
}


def is_valid_transition(current: ExecutionStatus, nxt: ExecutionStatus) -> bool:
    """Whether moving from ``current`` to ``nxt`` is allowed."""

    return nxt in _ALLOWED_TRANSITIONS.get(current, frozenset())
