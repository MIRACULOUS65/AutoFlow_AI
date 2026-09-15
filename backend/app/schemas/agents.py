"""Agent registry + runtime contracts (the AgentRuntime boundary with ML #1)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.domain.enums import AgentStatus, RiskClass, VerificationStatus
from app.schemas.common import Schema
from app.schemas.approval import CanonicalAction


class AgentTool(Schema):
    id: str
    name: str
    description: str | None = None


class AgentSummary(Schema):
    id: str
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    supported_tools: list[str] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.AVAILABLE
    version: str = "1.0"


class AgentDetail(AgentSummary):
    summary: str | None = None
    tools: list[AgentTool] = Field(default_factory=list)


# --- Runtime contracts (backend <-> agent runtime) -----------------------


class AgentRunRequest(Schema):
    task_id: str
    execution_id: str
    step_id: str
    objective: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    expected_state: str
    verification_requirements: list[str] = Field(default_factory=list)
    policy_context: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)


class ProposedAction(Schema):
    """An action an agent proposes. It is NOT executed until validated."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    target: str | None = None
    recipient: str | None = None
    resource: str | None = None
    risk_class: RiskClass = RiskClass.LOW
    material: bool = False

    def to_canonical(self, plan_version: int) -> CanonicalAction:
        return CanonicalAction(
            tool=self.tool,
            arguments=self.arguments,
            target=self.target,
            recipient=self.recipient,
            resource=self.resource,
            plan_version=plan_version,
        )


class AgentObservation(Schema):
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)


class AgentRunResult(Schema):
    agent_run_id: str
    status: str  # "completed" | "needs_approval" | "failed"
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    observations: list[AgentObservation] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    telemetry: dict[str, Any] = Field(default_factory=dict)


# --- Tool runtime contracts ----------------------------------------------


class ToolCall(Schema):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ToolResult(Schema):
    tool_call_id: str
    status: str  # "completed" | "failed"
    output: dict[str, Any] = Field(default_factory=dict)
    artifact_ref: str | None = None
    error: str | None = None


# --- Verification contracts ----------------------------------------------


class VerificationCheck(Schema):
    id: str
    passed: bool
    detail: str | None = None


class VerificationRequest(Schema):
    execution_id: str
    step_id: str
    checks: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class VerificationResult(Schema):
    verification_id: str
    status: VerificationStatus
    checks: list[VerificationCheck] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0


# --- Recovery contracts ---------------------------------------------------


class RecoveryRequest(Schema):
    execution_id: str
    step_id: str
    failure_reason: str
    attempt: int
    budget_remaining: int


class RecoveryOutcome(Schema):
    decision: str  # RecoveryDecision value
    reason: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


# --- Policy contracts -----------------------------------------------------


class PolicyDecision(Schema):
    allowed: bool
    requires_approval: bool = False
    risk_class: RiskClass = RiskClass.LOW
    reason: str | None = None
    category: str = "general"
