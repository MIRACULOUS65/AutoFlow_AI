"""Workflow, artifact, automation and audit contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from .common import (
    IdStr,
    Reference,
    Tenancy,
    Timestamped,
    VersionedModel,
    validate_id,
)
from .enums import (
    ActorType,
    ArtifactType,
    AutomationRunStatus,
    EventType,
    RiskClass,
    TriggerKind,
)


class WorkflowStep(VersionedModel):
    """A semantic step in a reusable workflow (never raw coordinates)."""

    name: str = Field(min_length=1, max_length=128)
    capability: str = Field(min_length=1, max_length=128)
    parameters: dict = Field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    requires_approval: bool = False
    verifier: str | None = Field(default=None, max_length=128)


class WorkflowVersion(VersionedModel, Timestamped):
    """An immutable, versioned semantic workflow representation."""

    workflow_id: IdStr
    version: int = Field(ge=1)
    intent: str = Field(min_length=1, max_length=2000)
    capabilities: tuple[str, ...] = ()
    steps: tuple[WorkflowStep, ...]
    provenance: tuple[Reference, ...] = ()
    execution_refs: tuple[Reference, ...] = ()
    verified: bool = False

    @field_validator("workflow_id")
    @classmethod
    def _wid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="wf")

    @field_validator("steps")
    @classmethod
    def _steps_nonempty(cls, v: tuple[WorkflowStep, ...]) -> tuple[WorkflowStep, ...]:
        if not v:
            raise ValueError("workflow version must contain at least one step")
        return v

    @model_validator(mode="after")
    def _valid_depends(self) -> "WorkflowVersion":
        names = [s.name for s in self.steps]
        if len(names) != len(set(names)):
            raise ValueError("workflow step names must be unique")
        name_set = set(names)
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in name_set:
                    raise ValueError(f"step {step.name!r} depends on unknown {dep!r}")
                if dep == step.name:
                    raise ValueError(f"step {step.name!r} cannot depend on itself")
        return self


class Workflow(VersionedModel, Timestamped):
    """A named workflow pointing at its current version."""

    workflow_id: IdStr
    tenancy: Tenancy
    name: str = Field(min_length=1, max_length=128)
    current_version: int = Field(ge=1)

    @field_validator("workflow_id")
    @classmethod
    def _wid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="wf")


class WorkflowMemory(VersionedModel, Timestamped):
    """A workflow promoted into reusable memory. Must be verified (RULE 15)."""

    memory_id: IdStr
    workflow_id: IdStr
    version: int = Field(ge=1)
    tenancy: Tenancy
    verified: bool
    score: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("memory_id")
    @classmethod
    def _mid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="wmem")

    @field_validator("workflow_id")
    @classmethod
    def _wid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="wf")

    @model_validator(mode="after")
    def _must_be_verified(self) -> "WorkflowMemory":
        if not self.verified:
            raise ValueError("only verified workflows may enter canonical memory")
        return self


class Artifact(VersionedModel, Timestamped):
    """A first-class generated artifact (master prompt §39)."""

    artifact_id: IdStr
    execution_id: IdStr
    workflow_id: IdStr | None = None
    workflow_version: int | None = Field(default=None, ge=1)
    artifact_type: ArtifactType
    mime_type: str = Field(min_length=1, max_length=128)
    uri: str | None = Field(default=None, max_length=2048)
    content_hash: str = Field(min_length=8, max_length=128)
    source_refs: tuple[Reference, ...] = ()
    creator_agent: str | None = Field(default=None, max_length=64)
    verified: bool = False

    @field_validator("artifact_id")
    @classmethod
    def _aid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="art")

    @field_validator("execution_id")
    @classmethod
    def _eid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="exec")

    @field_validator("workflow_id")
    @classmethod
    def _wid(cls, v: str | None) -> str | None:
        return None if v is None else validate_id(v, expected_prefix="wf")


class AutomationDefinition(VersionedModel, Timestamped):
    """A reusable automation (master prompt §23). Uses the same engine."""

    automation_id: IdStr
    tenancy: Tenancy
    name: str = Field(min_length=1, max_length=128)
    trigger_kind: TriggerKind
    schedule: str | None = Field(default=None, max_length=128)
    event_name: str | None = Field(default=None, max_length=128)
    workflow_id: IdStr
    workflow_version: int = Field(ge=1)
    conditions: tuple[str, ...] = ()
    inputs: dict = Field(default_factory=dict)
    approval_required: bool = False
    max_retries: int = Field(default=0, ge=0, le=50)
    timeout_seconds: float = Field(default=3600.0, gt=0)
    max_concurrency: int = Field(default=1, ge=1)
    enabled: bool = True

    @field_validator("automation_id")
    @classmethod
    def _auid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="auto")

    @field_validator("workflow_id")
    @classmethod
    def _wid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="wf")

    @model_validator(mode="after")
    def _trigger_consistency(self) -> "AutomationDefinition":
        if self.trigger_kind == TriggerKind.SCHEDULE and not self.schedule:
            raise ValueError("schedule trigger requires a schedule expression")
        if self.trigger_kind == TriggerKind.EVENT and not self.event_name:
            raise ValueError("event trigger requires an event_name")
        if self.trigger_kind == TriggerKind.MANUAL and (self.schedule or self.event_name):
            raise ValueError("manual trigger must not define schedule/event")
        return self


class AutomationRun(VersionedModel, Timestamped):
    """A single run of an automation, which creates a task/execution."""

    run_id: IdStr
    automation_id: IdStr
    status: AutomationRunStatus = AutomationRunStatus.SCHEDULED
    task_id: IdStr | None = None
    execution_id: IdStr | None = None
    attempt: int = Field(default=1, ge=1)

    @field_validator("run_id")
    @classmethod
    def _rid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="arun")

    @field_validator("automation_id")
    @classmethod
    def _auid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="auto")

    @field_validator("task_id")
    @classmethod
    def _tid(cls, v: str | None) -> str | None:
        return None if v is None else validate_id(v, expected_prefix="task")

    @field_validator("execution_id")
    @classmethod
    def _eid(cls, v: str | None) -> str | None:
        return None if v is None else validate_id(v, expected_prefix="exec")


class ExecutionEvent(VersionedModel):
    """A structured event. The stream must be sufficient to rebuild state
    and must never contain secrets or hidden chain-of-thought (master §26)."""

    event_id: IdStr
    type: EventType
    occurred_at: datetime
    organization_id: IdStr
    workspace_id: IdStr
    task_id: IdStr | None = None
    execution_id: IdStr | None = None
    step_id: IdStr | None = None
    actor_type: ActorType
    actor_id: str = Field(min_length=1, max_length=80)
    data: dict = Field(default_factory=dict)

    @field_validator("event_id")
    @classmethod
    def _evid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="evt")

    @field_validator("organization_id")
    @classmethod
    def _org(cls, v: str) -> str:
        return validate_id(v, expected_prefix="org")

    @field_validator("workspace_id")
    @classmethod
    def _ws(cls, v: str) -> str:
        return validate_id(v, expected_prefix="ws")

    @field_validator("occurred_at")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware (UTC)")
        return v

    _FORBIDDEN_KEYS = frozenset(
        {"api_key", "apikey", "password", "secret", "token", "authorization",
         "access_token", "client_secret", "chain_of_thought", "reasoning_trace"}
    )

    @model_validator(mode="after")
    def _no_secrets(self) -> "ExecutionEvent":
        lowered = {str(k).lower() for k in self.data}
        leaked = lowered & self._FORBIDDEN_KEYS
        if leaked:
            raise ValueError(f"event data must not contain sensitive keys: {sorted(leaked)}")
        return self


class AuditEvent(VersionedModel):
    """An audit record for a consequential operation."""

    audit_id: IdStr
    organization_id: IdStr
    workspace_id: IdStr
    action: str = Field(min_length=1, max_length=128)
    actor_type: ActorType
    actor_id: str = Field(min_length=1, max_length=80)
    occurred_at: datetime
    outcome: str = Field(min_length=1, max_length=64)
    risk: RiskClass = RiskClass.LOW
    target_ref: Reference | None = None

    @field_validator("audit_id")
    @classmethod
    def _auid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="audit")

    @field_validator("organization_id")
    @classmethod
    def _org(cls, v: str) -> str:
        return validate_id(v, expected_prefix="org")

    @field_validator("workspace_id")
    @classmethod
    def _ws(cls, v: str) -> str:
        return validate_id(v, expected_prefix="ws")

    @field_validator("occurred_at")
    @classmethod
    def _tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware (UTC)")
        return v
