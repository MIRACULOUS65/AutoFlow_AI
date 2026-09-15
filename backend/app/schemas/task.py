"""Task contracts.

TaskRequest is the authoritative input boundary. The client never supplies an
authoritative status, plan, execution result, or approval result — the backend
owns those. We accept both `goal` (Backend PRD) and `input.text` (API spec) for
frontend compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import TaskStatus, VerificationStatus
from app.schemas.common import Schema


class Constraint(Schema):
    kind: str
    value: Any | None = None


class AttachmentReference(Schema):
    file_id: str | None = None
    attachment_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size: int | None = None
    content_hash: str | None = None


class TaskInput(BaseModel):
    text: str


class TaskRequest(BaseModel):
    """Input contract for POST /tasks."""

    workspace_id: str
    goal: str | None = None
    input: TaskInput | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    attachments: list[AttachmentReference] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0, le=10)
    execution_mode: str = "autonomous_with_approval"
    client_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_goal_text(self) -> TaskRequest:
        if not self.resolved_goal.strip():
            raise ValueError("A goal (goal or input.text) is required.")
        return self

    @property
    def resolved_goal(self) -> str:
        if self.goal:
            return self.goal
        if self.input:
            return self.input.text
        return ""


class TaskCreateResponse(Schema):
    task_id: str
    execution_id: str
    status: TaskStatus
    created_at: datetime


class TaskSummary(Schema):
    """List-view task representation, aligned with the frontend Task model."""

    id: str
    workspace_id: str
    name: str
    goal: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    execution_id: str | None = None
    workflow_id: str | None = None
    plan_version: str
    assigned_agent_id: str | None = None
    current_step_id: str | None = None
    duration_ms: int = 0
    verification: VerificationStatus | None = None
    priority: int = 0


class TaskAttachmentOut(Schema):
    id: str
    filename: str
    mime_type: str | None = None
    size: int | None = None


class TaskDetail(TaskSummary):
    """Detail-view task: summary + related resources (no hidden reasoning)."""

    normalized_goal: str | None = None
    failure_reason: str | None = None
    attachments: list[TaskAttachmentOut] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    approval_ids: list[str] = Field(default_factory=list)
    step_ids: list[str] = Field(default_factory=list)
