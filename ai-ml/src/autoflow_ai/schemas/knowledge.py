"""Knowledge, context and memory contracts.

Retrieved content carries provenance and a trust level; it is *data*, never
instructions. Authorization is represented explicitly (permissions_scope) and
enforced outside similarity search.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .common import (
    IdStr,
    Reference,
    Tenancy,
    Timestamped,
    VersionedModel,
    validate_id,
)
from .enums import MemoryKind, TrustLevel


class KnowledgeChunk(VersionedModel, Timestamped):
    """A retrievable chunk with full provenance (master prompt §8)."""

    chunk_id: IdStr
    document_id: IdStr
    source_id: IdStr
    tenancy: Tenancy
    text: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    permissions_scope: frozenset[str] = frozenset()
    source_type: str = Field(min_length=1, max_length=64)
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    section: str | None = Field(default=None, max_length=256)
    page: int | None = Field(default=None, ge=0)
    content_hash: str = Field(min_length=8, max_length=128)

    @field_validator("chunk_id")
    @classmethod
    def _cid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="chunk")

    @field_validator("document_id")
    @classmethod
    def _did(cls, v: str) -> str:
        return validate_id(v, expected_prefix="doc")

    @field_validator("source_id")
    @classmethod
    def _srcid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="src")


class ContextItem(VersionedModel):
    """One ranked, trust-tagged item placed into an assembled context."""

    item_ref: Reference
    trust_level: TrustLevel
    tokens: int = Field(ge=0)
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    section: str = Field(min_length=1, max_length=64)


class ContextBundle(VersionedModel):
    """Assembled, budgeted context for a model call (BACKEND §17).

    Ordered sections keep untrusted content separated from system policy and
    task instructions. Token accounting must respect the budget.
    """

    bundle_id: IdStr
    task_id: IdStr
    items: tuple[ContextItem, ...] = ()
    token_budget: int = Field(gt=0)
    reserved_output_tokens: int = Field(default=0, ge=0)

    @field_validator("bundle_id")
    @classmethod
    def _bid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="ctx")

    @field_validator("task_id")
    @classmethod
    def _tid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="task")

    @property
    def used_tokens(self) -> int:
        return sum(i.tokens for i in self.items)

    @model_validator(mode="after")
    def _within_budget(self) -> "ContextBundle":
        if self.used_tokens + self.reserved_output_tokens > self.token_budget:
            raise ValueError(
                "context exceeds token budget: "
                f"used={self.used_tokens} reserved={self.reserved_output_tokens} "
                f"budget={self.token_budget}"
            )
        return self


class MemoryItem(VersionedModel, Timestamped):
    """A stored memory entry, scoped and typed."""

    memory_id: IdStr
    kind: MemoryKind
    tenancy: Tenancy
    content_ref: Reference
    trust_level: TrustLevel = TrustLevel.TRUSTED
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    verified: bool = False

    @field_validator("memory_id")
    @classmethod
    def _mid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="mem")

    @model_validator(mode="after")
    def _workflow_memory_must_be_verified(self) -> "MemoryItem":
        # Only sufficiently verified executions become canonical workflow
        # memory (RULE 15, FR-15).
        if self.kind == MemoryKind.WORKFLOW and not self.verified:
            raise ValueError("workflow memory must be verified before storage")
        return self
