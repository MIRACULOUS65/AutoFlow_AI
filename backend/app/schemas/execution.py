"""Execution contracts and execution context snapshot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.domain.enums import ExecutionStatus, VerificationStatus
from app.schemas.common import Schema
from app.schemas.plan import PlanStepOut


class ExecutionBudget(Schema):
    max_attempts: int = 5
    max_runtime_seconds: int = 3600
    max_replans: int = 3
    max_model_calls: int = 100
    max_tool_cost: float = 100.0


class ExecutionContextSnapshot(Schema):
    """Deterministic context captured when the execution is created."""

    organization_id: str
    workspace_id: str
    permissions: list[str] = Field(default_factory=list)
    policy_profile: str = "standard"
    tool_allowlist: list[str] = Field(default_factory=list)
    context_namespace: str
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)


class ExecutionSummary(Schema):
    id: str
    task_id: str
    task_name: str | None = None
    workspace_id: str
    status: ExecutionStatus
    agent_id: str | None = None
    plan_version: int
    current_step_id: str | None = None
    attempt_count: int = 0
    cancel_requested: bool = False
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = 0
    verification: VerificationStatus | None = None
    created_at: datetime
    updated_at: datetime


class ExecutionDetail(ExecutionSummary):
    plan_id: str | None = None
    version: int = 0  # optimistic concurrency version
    budget: ExecutionBudget | None = None
    steps: list[PlanStepOut] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)


class Observation(Schema):
    observation_id: str
    step_id: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
