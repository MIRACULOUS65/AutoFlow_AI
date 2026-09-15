"""Memory data models: session, semantic workflow, versions, graph, scoring."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from ..schemas.common import AutoFlowModel, VersionedModel, utcnow
from ..schemas.enums import StrEnum


# ---------------------------------------------------------------------------
# enums
# ---------------------------------------------------------------------------


class WorkflowStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    BLOCKED = "blocked"
    ARCHIVED = "archived"


class CompatibilityLevel(StrEnum):
    COMPATIBLE = "compatible"
    PARTIALLY_COMPATIBLE = "partially_compatible"
    INCOMPATIBLE = "incompatible"


class ReuseMode(StrEnum):
    REUSE_EXACT = "reuse_exact"
    ADAPT_PARAMETERS = "adapt_parameters"
    ADAPT_PLAN = "adapt_plan"
    IGNORE_MEMORY = "ignore_memory"


# ---------------------------------------------------------------------------
# session memory
# ---------------------------------------------------------------------------


class SessionMemory(AutoFlowModel):
    """Short-lived, bounded per-execution state (safe to serialize)."""

    task_id: str
    execution_id: str | None = None
    current_workflow: str | None = None
    current_step: str | None = None
    variables: dict = Field(default_factory=dict)
    observations: tuple[str, ...] = ()
    tool_results: tuple[str, ...] = ()
    verification_results: tuple[str, ...] = ()
    approval_state: str | None = None
    recovery_state: str | None = None
    max_history: int = Field(default=50, ge=1, le=1000)

    def _bounded(self, items: tuple[str, ...]) -> tuple[str, ...]:
        return items[-self.max_history :]

    def add_observation(self, text: str) -> None:
        self.observations = self._bounded(self.observations + (text,))

    def add_tool_result(self, text: str) -> None:
        self.tool_results = self._bounded(self.tool_results + (text,))

    def snapshot(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def restore(cls, data: dict) -> "SessionMemory":
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# semantic workflow
# ---------------------------------------------------------------------------


class WorkflowParameter(AutoFlowModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=512)
    required: bool = True
    default: str | None = None


class WorkflowStep(AutoFlowModel):
    """A semantic step (never raw coordinates)."""

    name: str = Field(min_length=1, max_length=128)
    capability: str = Field(min_length=1, max_length=128)
    tool: str | None = Field(default=None, max_length=128)
    parameters: dict = Field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    requires_approval: bool = False
    verifier: str | None = Field(default=None, max_length=128)

    @field_validator("name")
    @classmethod
    def _no_coordinates(cls, v: str) -> str:
        # canonical steps must be semantic, not click(x,y)
        if re.search(r"\b\d{2,4}\s*,\s*\d{2,4}\b", v) or v.lower().startswith("click("):
            raise ValueError("workflow step names must be semantic, not coordinates")
        return v


class SemanticWorkflow(AutoFlowModel):
    """The canonical WHAT-not-HOW representation of a workflow."""

    intent: str = Field(min_length=1, max_length=2000)
    capabilities: tuple[str, ...] = ()
    applications: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    steps: tuple[WorkflowStep, ...]
    parameters: tuple[WorkflowParameter, ...] = ()
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
    approval_points: tuple[str, ...] = ()
    recovery_rules: tuple[str, ...] = ()
    verification_rules: tuple[str, ...] = ()

    @field_validator("steps")
    @classmethod
    def _steps_nonempty(cls, v):
        if not v:
            raise ValueError("workflow must contain at least one step")
        return v

    @model_validator(mode="after")
    def _valid_dependencies(self) -> "SemanticWorkflow":
        names = [s.name for s in self.steps]
        if len(names) != len(set(names)):
            raise ValueError("workflow step names must be unique")
        name_set = set(names)
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in name_set:
                    raise ValueError(f"step {step.name!r} depends on unknown {dep!r}")
        return self


class WorkflowScore(AutoFlowModel):
    """Explainable score components (not probabilistic confidence)."""

    semantic: float = Field(default=0.0, ge=0.0, le=1.0)
    compatibility: float = Field(default=0.0, ge=0.0, le=1.0)
    success: float = Field(default=0.0, ge=0.0, le=1.0)
    recency: float = Field(default=0.0, ge=0.0, le=1.0)
    total: float = Field(default=0.0, ge=0.0, le=1.0)


class WorkflowProvenance(AutoFlowModel):
    source_execution_ids: tuple[str, ...] = ()
    source_task_id: str | None = None
    source_workspace: str | None = None
    verification_evidence: tuple[str, ...] = ()
    generator: str = "workflow_normalizer_v1"
    created_at: datetime = Field(default_factory=utcnow)


class WorkflowMemory(VersionedModel):
    """A stored, versioned reusable workflow (metadata + semantic body)."""

    workflow_id: str = Field(min_length=1, max_length=128)
    canonical_name: str = Field(min_length=1, max_length=128)
    workflow: SemanticWorkflow
    version: int = Field(ge=1)
    status: WorkflowStatus = WorkflowStatus.CANDIDATE
    tenant_id: str = Field(min_length=1, max_length=80)
    workspace_id: str = Field(min_length=1, max_length=80)
    permission_scope: tuple[str, ...] = ()
    usage_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    verified_count: int = Field(default=0, ge=0)
    content_hash: str = Field(min_length=8, max_length=128)
    provenance: WorkflowProvenance = Field(default_factory=WorkflowProvenance)
    parent_version: int | None = Field(default=None, ge=1)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = None

    @property
    def verified_success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total else 0.0

    def capability_tags(self) -> str:
        return ",".join(sorted(self.workflow.capabilities))

    def tool_tags(self) -> str:
        return ",".join(sorted(self.workflow.tools))

    def searchable_text(self) -> str:
        parts = [self.canonical_name, self.workflow.intent]
        parts.extend(self.workflow.capabilities)
        parts.extend(s.name for s in self.workflow.steps)
        return " ".join(parts)


class WorkflowVersion(AutoFlowModel):
    """Immutable version record."""

    workflow_id: str
    version: int = Field(ge=1)
    content_hash: str
    created_at: datetime = Field(default_factory=utcnow)
    source_execution_ids: tuple[str, ...] = ()
    change_summary: str = ""
    parent_version: int | None = None


class WorkflowCandidate(AutoFlowModel):
    """A not-yet-promoted workflow derived from a verified execution."""

    candidate_id: str = Field(min_length=1, max_length=128)
    canonical_name: str
    workflow: SemanticWorkflow
    tenant_id: str
    workspace_id: str
    permission_scope: tuple[str, ...] = ()
    source_execution_ids: tuple[str, ...] = ()
    source_task_id: str | None = None
    verified: bool = False
    verification_evidence: tuple[str, ...] = ()
    content_hash: str = ""

    @model_validator(mode="after")
    def _fill_hash(self) -> "WorkflowCandidate":
        if not self.content_hash:
            object.__setattr__(self, "content_hash", workflow_content_hash(self.workflow))
        return self


class WorkflowPromotionDecision(AutoFlowModel):
    promoted: bool
    workflow_id: str | None = None
    version: int | None = None
    reason: str = ""
    rejected_reasons: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# graph memory
# ---------------------------------------------------------------------------


class GraphNode(AutoFlowModel):
    node_id: str = Field(min_length=1, max_length=160)
    kind: str = Field(min_length=1, max_length=64)  # application/tool/action/artifact/workflow/capability
    label: str = Field(min_length=1, max_length=256)


class GraphEdge(AutoFlowModel):
    from_id: str
    to_id: str
    relation: str = Field(min_length=1, max_length=64)  # USES/PRODUCES/REQUIRES/DEPENDS_ON/VERIFIED_BY/AVAILABLE_IN


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


_SECRET_PATTERNS = [
    re.compile(r"nvapi-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"ms-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|access[_-]?token)\b\s*[=:]\s*\S+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def contains_secret(text: str) -> bool:
    """Heuristic detection of secret-like content in a workflow body."""

    return any(p.search(text) for p in _SECRET_PATTERNS)


def workflow_content_hash(workflow: SemanticWorkflow) -> str:
    """Canonical hash over semantic content + params + tools + verification."""

    payload = {
        "intent": workflow.intent,
        "steps": [
            {
                "name": s.name,
                "capability": s.capability,
                "tool": s.tool,
                "depends_on": sorted(s.depends_on),
                "requires_approval": s.requires_approval,
                "verifier": s.verifier,
            }
            for s in workflow.steps
        ],
        "parameters": sorted(p.name for p in workflow.parameters),
        "tools": sorted(workflow.tools),
        "approval_points": sorted(workflow.approval_points),
        "verification_rules": sorted(workflow.verification_rules),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
