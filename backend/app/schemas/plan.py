"""Plan and PlanStep contracts.

Plans are immutable versions produced by the orchestrator. The backend stores
what the orchestrator returns; it never invents agent-specific logic. A plan is
a graph of steps with dependencies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.domain.enums import PlanValidationStatus, RiskClass, StepStatus
from app.schemas.common import Schema


class RetryPolicy(Schema):
    max_attempts: int = 3
    backoff_seconds: float = 1.0


class VerificationCheckSpec(Schema):
    id: str
    kind: str = "STRUCTURAL"
    description: str | None = None


class PlanStepSpec(Schema):
    """A step as produced by the orchestrator (contract with ML #2)."""

    step_id: str
    index: int
    objective: str
    title: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    agent_profile: str
    allowed_tools: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_state: str
    preconditions: list[str] = Field(default_factory=list)
    verification_checks: list[VerificationCheckSpec] = Field(default_factory=list)
    risk_class: RiskClass = RiskClass.LOW
    timeout_seconds: int = 300
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    recovery_budget: int = 3
    requires_approval: bool = False


class PlanGraph(Schema):
    steps: list[PlanStepSpec]


class Plan(Schema):
    """A full immutable plan version returned by the orchestrator."""

    plan_id: str
    task_id: str
    version: int
    graph: PlanGraph
    generated_by: str = "orchestrator"
    validation_status: PlanValidationStatus = PlanValidationStatus.DRAFT
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    required_approvals: int = 0
    plan_hash: str | None = None


class PlanStepOut(Schema):
    """Persisted step state for the API / frontend TaskStep."""

    id: str
    index: int
    title: str
    objective: str
    agent_id: str
    status: StepStatus
    verification: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    expected_state: str
    current_state: str = ""
    attempts: int = 0
    max_attempts: int = 3
    requires_approval: bool = False
    risk_class: RiskClass = RiskClass.LOW


class PlanSummary(Schema):
    plan_id: str
    task_id: str
    version: int
    validation_status: PlanValidationStatus
    required_approvals: int
    plan_hash: str | None = None
    created_at: datetime


class PlanDetail(PlanSummary):
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    steps: list[PlanStepOut] = Field(default_factory=list)


class ReplanRequest(Schema):
    task_id: str
    execution_id: str
    failed_step_id: str
    reason: str | None = None


class PlanFragment(Schema):
    """A partial replan produced by the orchestrator during recovery."""

    steps: list[PlanStepSpec]
    replaces_step_ids: list[str] = Field(default_factory=list)
