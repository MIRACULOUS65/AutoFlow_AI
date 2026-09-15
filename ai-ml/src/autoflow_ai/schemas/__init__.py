"""AutoFlow AI contract schemas (Phase 1).

Every cross-subsystem data shape is a strict, versioned Pydantic model. Import
the public names from this package rather than the individual modules.
"""

from __future__ import annotations

from .agents import (
    AgentDefinition,
    AgentRun,
    AgentRunInput,
    ProposedAction,
)
from .approvals import ApprovalDecision, ApprovalRequest
from .common import (
    AutoFlowModel,
    Principal,
    Reference,
    Tenancy,
    Timestamped,
    VersionedModel,
    canonical_hash,
    utcnow,
    validate_id,
)
from .enums import (
    ActionType,
    ActorType,
    AgentKind,
    ApprovalStatus,
    ArtifactType,
    AutomationRunStatus,
    DeploymentType,
    EventType,
    ExecutionStatus,
    HealthState,
    MemoryKind,
    Modality,
    ModelRole,
    RecoveryStrategy,
    RiskClass,
    StepStatus,
    TERMINAL_EXECUTION_STATES,
    TriggerKind,
    TrustLevel,
    VerificationKind,
    VerificationStatus,
)
from .execution import (
    Execution,
    ExecutionBudget,
    ExecutionStep,
    Observation,
    RecoveryDecision,
    VerificationCheck,
    VerificationResult,
    is_valid_transition,
)
from .knowledge import (
    ContextBundle,
    ContextItem,
    KnowledgeChunk,
    MemoryItem,
)
from .models import (
    ModelCapability,
    ModelDefinition,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)
from .tasks import (
    Attachment,
    NormalizedTask,
    TaskEdge,
    TaskGraph,
    TaskNode,
    TaskRequest,
    VerificationRequirement,
)
from .tools import (
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    validate_tool_arguments,
)
from .workflows import (
    Artifact,
    AuditEvent,
    AutomationDefinition,
    AutomationRun,
    ExecutionEvent,
    Workflow,
    WorkflowMemory,
    WorkflowStep,
    WorkflowVersion,
)

__all__ = [
    # base / common
    "AutoFlowModel",
    "VersionedModel",
    "Principal",
    "Reference",
    "Tenancy",
    "Timestamped",
    "canonical_hash",
    "utcnow",
    "validate_id",
    # enums
    "ActionType",
    "ActorType",
    "AgentKind",
    "ApprovalStatus",
    "ArtifactType",
    "AutomationRunStatus",
    "DeploymentType",
    "EventType",
    "ExecutionStatus",
    "HealthState",
    "MemoryKind",
    "Modality",
    "ModelRole",
    "RecoveryStrategy",
    "RiskClass",
    "StepStatus",
    "TERMINAL_EXECUTION_STATES",
    "TriggerKind",
    "TrustLevel",
    "VerificationKind",
    "VerificationStatus",
    # tasks / planning
    "Attachment",
    "TaskRequest",
    "NormalizedTask",
    "TaskNode",
    "TaskEdge",
    "TaskGraph",
    "VerificationRequirement",
    # models
    "ModelCapability",
    "ModelDefinition",
    "ModelRequest",
    "ModelResponse",
    "ModelUsage",
    # tools
    "ToolDefinition",
    "ToolCallRequest",
    "ToolCallResult",
    "validate_tool_arguments",
    # agents
    "AgentDefinition",
    "AgentRunInput",
    "ProposedAction",
    "AgentRun",
    # knowledge / context / memory
    "KnowledgeChunk",
    "ContextItem",
    "ContextBundle",
    "MemoryItem",
    # execution / observation / verification / recovery
    "Observation",
    "VerificationCheck",
    "VerificationResult",
    "RecoveryDecision",
    "ExecutionBudget",
    "ExecutionStep",
    "Execution",
    "is_valid_transition",
    # approvals
    "ApprovalRequest",
    "ApprovalDecision",
    # workflows / artifacts / automation / audit
    "WorkflowStep",
    "WorkflowVersion",
    "Workflow",
    "WorkflowMemory",
    "Artifact",
    "AutomationDefinition",
    "AutomationRun",
    "ExecutionEvent",
    "AuditEvent",
]
