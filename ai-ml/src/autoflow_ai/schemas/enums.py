"""Enumerations shared across AutoFlow AI contracts.

All enums are string-valued so they serialize deterministically to JSON and
remain human-readable in events and audit logs.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String enum whose ``str()`` and JSON form is the bare value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class RiskClass(StrEnum):
    """Risk classification for actions, steps and tools.

    Drives approval requirements and policy filtering. Ordering matters:
    higher risk requires stronger controls.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ModelRole(StrEnum):
    """Role a model can serve. A single model may serve multiple roles."""

    PLANNER = "planner"
    EXECUTOR = "executor"
    TOOL_CALLER = "tool_caller"
    VISION = "vision"
    CODING = "coding"
    EMBEDDING = "embedding"
    RERANKER = "reranker"


class Modality(StrEnum):
    """Input/output modality a model supports."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class DeploymentType(StrEnum):
    """Where a model is hosted."""

    CLOUD_API = "cloud_api"
    OPENAI_COMPATIBLE = "openai_compatible"
    SELF_HOSTED = "self_hosted"
    LOCAL = "local"


class HealthState(StrEnum):
    """Health of a model/provider."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AgentKind(StrEnum):
    """Specialist agent families over a shared runtime."""

    PLANNER = "planner"
    RESEARCH = "research"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    CODING = "coding"
    DATA_ANALYSIS = "data_analysis"
    COMMUNICATION = "communication"
    BROWSER = "browser"
    COMPUTER = "computer"
    QA = "qa"


class ActionType(StrEnum):
    """Kind of action an execution agent may propose."""

    TOOL_CALL = "tool_call"
    REQUEST_APPROVAL = "request_approval"
    REQUEST_CLARIFICATION = "request_clarification"
    ESCALATE = "escalate"
    NOOP = "noop"


class ExecutionStatus(StrEnum):
    """Canonical execution state machine.

    See EXECUTION_RUNTIME.md §3. Terminal states are marked in
    :data:`TERMINAL_EXECUTION_STATES`.
    """

    QUEUED = "queued"
    PLANNING = "planning"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    VERIFYING = "verifying"
    RECOVERY = "recovery"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    BLOCKED = "blocked"


TERMINAL_EXECUTION_STATES: frozenset[ExecutionStatus] = frozenset(
    {
        ExecutionStatus.COMPLETE,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.EXPIRED,
        ExecutionStatus.BLOCKED,
    }
)


class StepStatus(StrEnum):
    """Status of an individual execution step."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerificationStatus(StrEnum):
    """Result of verifying a step/artifact outcome."""

    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    NOT_RUN = "not_run"


class VerificationKind(StrEnum):
    """Category of verification check (EXECUTION_RUNTIME.md §9)."""

    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    UI_STATE = "ui_state"
    DATA = "data"
    ARTIFACT = "artifact"
    EXTERNAL = "external"


class RecoveryStrategy(StrEnum):
    """Bounded recovery ladder (EXECUTION_RUNTIME.md §10)."""

    RETRY = "retry"
    RE_OBSERVE = "re_observe"
    RE_RESOLVE = "re_resolve"
    ALTERNATE_PATH = "alternate_path"
    VISUAL_GROUNDING = "visual_grounding"
    REPLAN = "replan"
    HUMAN_ESCALATION = "human_escalation"
    ABORT = "abort"


class ApprovalStatus(StrEnum):
    """Lifecycle of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MemoryKind(StrEnum):
    """Types of memory (AGENT_BRAIN / PROJECT_VISION §17)."""

    SESSION = "session"
    ENTERPRISE_KNOWLEDGE = "enterprise_knowledge"
    WORKFLOW = "workflow"
    GRAPH = "graph"


class TrustLevel(StrEnum):
    """Trust level for retrieved/stored content.

    Retrieved documents are data, never instructions.
    """

    SYSTEM = "system"
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class ArtifactType(StrEnum):
    """First-class artifact kinds (master prompt §39)."""

    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"
    IMAGE = "image"
    CODE = "code"
    TEST_REPORT = "test_report"
    EMAIL_DRAFT = "email_draft"
    TEXT = "text"


class TriggerKind(StrEnum):
    """Automation trigger types (master prompt §23)."""

    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"


class AutomationRunStatus(StrEnum):
    """Status of a single automation run."""

    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class EventType(StrEnum):
    """Canonical execution event types (master prompt §26).

    The event stream must be sufficient to rebuild execution state.
    """

    TASK_CREATED = "task.created"
    TASK_NORMALIZED = "task.normalized"
    TASK_PLANNED = "task.planned"
    PLAN_VALIDATED = "plan.validated"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    MODEL_CALLED = "model.called"
    TOOL_REQUESTED = "tool.requested"
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    OBSERVATION_CREATED = "observation.created"
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_PASSED = "verification.passed"
    VERIFICATION_FAILED = "verification.failed"
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_COMPLETED = "recovery.completed"
    REPLAN_CREATED = "replan.created"
    ARTIFACT_CREATED = "artifact.created"
    EXECUTION_PAUSED = "execution.paused"
    EXECUTION_RESUMED = "execution.resumed"
    EXECUTION_CANCELLED = "execution.cancelled"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    WORKFLOW_MEMORY_CREATED = "workflow.memory.created"


class ActorType(StrEnum):
    """Who/what produced an event."""

    USER = "user"
    AGENT = "agent"
    WORKER = "worker"
    SYSTEM = "system"
    SCHEDULER = "scheduler"
