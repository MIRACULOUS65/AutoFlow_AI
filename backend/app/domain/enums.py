"""Domain enums — the canonical vocabulary of the control plane.

These values are part of the frozen contract shared with the frontend and the
ML team. They must not change casually.
"""

from __future__ import annotations

from enum import StrEnum


class TaskStatus(StrEnum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    VALIDATING = "VALIDATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    RECOVERY = "RECOVERY"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"


# Executions share the task lifecycle vocabulary.
ExecutionStatus = TaskStatus


class StepStatus(StrEnum):
    WAITING = "WAITING"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETE = "COMPLETE"
    APPROVAL = "APPROVAL"
    FAILED = "FAILED"
    RECOVERY = "RECOVERY"
    SKIPPED = "SKIPPED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class RiskClass(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecoveryDecision(StrEnum):
    RETRY = "RETRY"
    REOBSERVE = "REOBSERVE"
    RERESOLVE = "RERESOLVE"
    ALTERNATE_PATH = "ALTERNATE_PATH"
    REPLAN = "REPLAN"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"
    FAIL = "FAIL"


class VerificationStatus(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class PlanValidationStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    INVALID = "INVALID"


class AgentStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    IDLE = "IDLE"
    OFFLINE = "OFFLINE"


class ArtifactType(StrEnum):
    DOCX = "DOCX"
    XLSX = "XLSX"
    PPTX = "PPTX"
    PDF = "PDF"
    CSV = "CSV"
    JSON = "JSON"
    CODE = "CODE"
    IMAGE = "IMAGE"
    TEST_REPORT = "TEST_REPORT"
    EMAIL_DRAFT = "EMAIL_DRAFT"
    MESSAGE_DRAFT = "MESSAGE_DRAFT"


class Role(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class ActorType(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    ORCHESTRATOR = "ORCHESTRATOR"
    AGENT = "AGENT"
    WORKER = "WORKER"


class EventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_CANCEL_REQUESTED = "task.cancel_requested"

    PLAN_CREATED = "plan.created"
    PLAN_VALIDATED = "plan.validated"
    PLAN_INVALID = "plan.invalid"

    EXECUTION_STARTED = "execution.started"
    EXECUTION_PAUSED = "execution.paused"
    EXECUTION_RESUMED = "execution.resumed"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_CANCELLED = "execution.cancelled"

    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"

    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"

    TOOL_REQUESTED = "tool.requested"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"

    OBSERVATION_CREATED = "observation.created"

    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"

    RECOVERY_STARTED = "recovery.started"
    RECOVERY_REPLANNED = "recovery.replanned"

    ARTIFACT_CREATED = "artifact.created"


# Sets used for status classification / filtering.
ACTIVE_TASK_STATUSES = frozenset(
    {
        TaskStatus.QUEUED,
        TaskStatus.PLANNING,
        TaskStatus.VALIDATING,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.RUNNING,
        TaskStatus.VERIFYING,
        TaskStatus.RECOVERY,
    }
)

TERMINAL_TASK_STATUSES = frozenset(
    {
        TaskStatus.COMPLETE,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.EXPIRED,
    }
)
