"""Approval contracts.

Approval is a first-class durable object. It binds to an exact action identity
via an action hash and a plan version; if the material action changes, the
approval is invalidated.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.enums import ApprovalStatus, RiskClass
from app.schemas.common import Schema


class EvidenceItem(Schema):
    id: str
    label: str
    passed: bool


class ApprovalSummary(Schema):
    id: str
    task_id: str
    task_name: str | None = None
    workspace_id: str
    execution_id: str | None = None
    step_id: str | None = None
    plan_version: int | None = None
    action: str
    category: str
    risk_class: RiskClass
    status: ApprovalStatus
    requested_at: datetime
    resolved_at: datetime | None = None
    expires_at: datetime | None = None


class ApprovalDetail(ApprovalSummary):
    action_hash: str
    target: str | None = None
    attachment: str | None = None
    plan_label: str | None = None
    risk: str | None = None
    reason: str | None = None
    requested_by: str | None = None
    approver: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ApprovalDecisionRequest(Schema):
    reason: str | None = None


class CanonicalAction(Schema):
    """Canonical representation of a material action, used for the action hash."""

    tool: str
    arguments: dict = Field(default_factory=dict)
    target: str | None = None
    recipient: str | None = None
    resource: str | None = None
    plan_version: int
