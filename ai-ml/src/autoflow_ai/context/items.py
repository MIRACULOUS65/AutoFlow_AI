"""ContextItem and section definitions."""

from __future__ import annotations

import hashlib

from pydantic import Field, field_validator

from ..schemas.common import AutoFlowModel, VersionedModel
from ..schemas.enums import StrEnum
from .trust import TrustLevel


class ContextSection(StrEnum):
    """Canonical context sections, in authority order (see SECTION_ORDER)."""

    SYSTEM_POLICY = "system_policy"
    TASK_INSTRUCTION = "task_instruction"
    IDENTITY = "identity"
    WORKSPACE = "workspace"
    PERMISSIONS = "permissions"
    CURRENT_WORKFLOW = "current_workflow"
    CURRENT_STEP = "current_step"
    AUTHORIZED_KNOWLEDGE = "authorized_knowledge"
    WORKFLOW_MEMORY = "workflow_memory"
    CURRENT_OBSERVATION = "current_observation"
    TOOL_RESULTS = "tool_results"
    RECOVERY_HISTORY = "recovery_history"
    APPROVAL_STATE = "approval_state"
    OUTPUT_CONTRACT = "output_contract"


# Canonical ordering used for prompt assembly and budgeting.
SECTION_ORDER: tuple[ContextSection, ...] = (
    ContextSection.SYSTEM_POLICY,
    ContextSection.TASK_INSTRUCTION,
    ContextSection.IDENTITY,
    ContextSection.WORKSPACE,
    ContextSection.PERMISSIONS,
    ContextSection.CURRENT_WORKFLOW,
    ContextSection.CURRENT_STEP,
    ContextSection.AUTHORIZED_KNOWLEDGE,
    ContextSection.WORKFLOW_MEMORY,
    ContextSection.CURRENT_OBSERVATION,
    ContextSection.TOOL_RESULTS,
    ContextSection.RECOVERY_HISTORY,
    ContextSection.APPROVAL_STATE,
    ContextSection.OUTPUT_CONTRACT,
)

# Sections that hold protected/authorized knowledge require authorization
# metadata (tenant/workspace/permission scope) before an item may enter them.
PROTECTED_SECTIONS = frozenset(
    {ContextSection.AUTHORIZED_KNOWLEDGE, ContextSection.WORKFLOW_MEMORY}
)


class ContextItem(VersionedModel):
    """A single, typed, trust-classified piece of context."""

    id: str = Field(min_length=1, max_length=128)
    section: ContextSection
    content: str
    trust_level: TrustLevel
    source_type: str = Field(default="inline", max_length=64)
    source_id: str | None = Field(default=None, max_length=256)
    tenant_id: str | None = Field(default=None, max_length=80)
    workspace_id: str | None = Field(default=None, max_length=80)
    permission_scope: frozenset[str] = frozenset()
    provenance: dict = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness: float = Field(default=1.0, ge=0.0, le=1.0)
    token_estimate: int = Field(default=0, ge=0)

    @field_validator("content")
    @classmethod
    def _content_nonempty(cls, v: str) -> str:
        if v is None:
            raise ValueError("content must not be None")
        return v

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def has_authorization_metadata(self) -> bool:
        return bool(self.tenant_id and self.workspace_id)

    def dedupe_key(self) -> str:
        """Key used to detect duplicate content across sources."""

        normalized = " ".join(self.content.split()).lower()
        return hashlib.sha256(f"{self.section}:{normalized}".encode("utf-8")).hexdigest()
