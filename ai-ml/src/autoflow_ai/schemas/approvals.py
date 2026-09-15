"""Approval contracts.

Approval is a first-class workflow state. An approval binds to an exact plan
version and action hash; any material change after approval invalidates it
(RULE 6/7, master prompt §15).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from .common import IdStr, Reference, Timestamped, VersionedModel, validate_id
from .enums import ApprovalStatus, RiskClass


class ApprovalRequest(VersionedModel, Timestamped):
    """A request to approve a consequential action."""

    approval_id: IdStr
    execution_id: IdStr
    step_id: IdStr
    plan_version: int = Field(ge=1)
    action_hash: str = Field(min_length=8, max_length=128)
    risk: RiskClass
    summary: str = Field(min_length=1, max_length=2000)
    evidence: tuple[Reference, ...] = ()
    requested_by: IdStr
    approver: IdStr | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    expires_at: datetime | None = None

    @field_validator("approval_id")
    @classmethod
    def _apid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="appr")

    @field_validator("execution_id")
    @classmethod
    def _eid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="exec")

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")

    @field_validator("requested_by")
    @classmethod
    def _rb(cls, v: str) -> str:
        return validate_id(v, expected_prefix="user")

    @field_validator("approver")
    @classmethod
    def _ap(cls, v: str | None) -> str | None:
        return None if v is None else validate_id(v, expected_prefix="user")

    @field_validator("expires_at")
    @classmethod
    def _tz(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware (UTC)")
        return v

    @model_validator(mode="after")
    def _high_risk_only(self) -> "ApprovalRequest":
        # Approvals are for medium+ risk actions; low-risk should not gate.
        if self.risk == RiskClass.LOW:
            raise ValueError("approval requests are only for medium+ risk actions")
        return self

    def binds_to(self, *, plan_version: int, action_hash: str) -> bool:
        """Whether this approval is valid for a given plan/action.

        A mismatch means the plan or action changed materially after approval
        and a new approval is required.
        """

        return self.plan_version == plan_version and self.action_hash == action_hash


class ApprovalDecision(VersionedModel, Timestamped):
    """The recorded decision on an approval request."""

    approval_id: IdStr
    decision: ApprovalStatus
    approver: IdStr
    plan_version: int = Field(ge=1)
    action_hash: str = Field(min_length=8, max_length=128)
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("approval_id")
    @classmethod
    def _apid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="appr")

    @field_validator("approver")
    @classmethod
    def _ap(cls, v: str) -> str:
        return validate_id(v, expected_prefix="user")

    @model_validator(mode="after")
    def _terminal_decision(self) -> "ApprovalDecision":
        if self.decision == ApprovalStatus.PENDING:
            raise ValueError("a decision cannot be PENDING")
        return self
