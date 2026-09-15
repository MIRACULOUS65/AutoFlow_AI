"""RAG data models (documents, chunks, retrieval results, evidence)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from ..schemas.common import AutoFlowModel, VersionedModel, utcnow
from ..schemas.enums import StrEnum


class RetrievalStatus(StrEnum):
    """Operational status of a retrieval call.

    NO_RESULTS and NO_AUTHORIZED_EVIDENCE are DIFFERENT states: the first means
    nothing matched; the second means matches existed but none were authorized.
    """

    SUCCESS = "success"
    NO_RESULTS = "no_results"
    NO_AUTHORIZED_EVIDENCE = "no_authorized_evidence"
    PARTIAL = "partial"
    FAILED = "failed"


class DocumentVersion(AutoFlowModel):
    """A version of a document keyed by content hash."""

    document_id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    content_hash: str = Field(min_length=8, max_length=128)
    ingested_at: datetime = Field(default_factory=utcnow)
    source_metadata: dict = Field(default_factory=dict)


class Document(VersionedModel):
    """A normalized ingested document (identity is the stable document_id)."""

    document_id: str = Field(min_length=1, max_length=128)
    source_id: str = Field(min_length=1, max_length=256)
    file_name: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=80)
    workspace_id: str = Field(min_length=1, max_length=80)
    version: int = Field(default=1, ge=1)
    content_hash: str = Field(min_length=8, max_length=128)
    source_type: str = Field(min_length=1, max_length=64)
    permission_scope: tuple[str, ...] = ()
    page_count: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict = Field(default_factory=dict)


class Chunk(VersionedModel):
    """A retrievable chunk with full source identity."""

    chunk_id: str = Field(min_length=1, max_length=160)
    document_id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    text: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    token_estimate: int = Field(default=0, ge=0)
    content_hash: str = Field(min_length=8, max_length=128)
    page: int | None = Field(default=None, ge=0)
    section: str | None = Field(default=None, max_length=256)

    # scoping metadata carried into the vector store for physical filtering
    tenant_id: str = Field(min_length=1, max_length=80)
    workspace_id: str = Field(min_length=1, max_length=80)
    source_id: str = Field(min_length=1, max_length=256)
    source_type: str = Field(min_length=1, max_length=64)
    file_name: str = Field(min_length=1, max_length=512)
    permission_scope: tuple[str, ...] = ()

    def store_metadata(self) -> dict:
        """Flat, Chroma-safe metadata (only scalars/strings)."""

        return {
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "version": self.version,
            "chunk_id": self.chunk_id,
            "source_type": self.source_type,
            "file_name": self.file_name,
            "content_hash": self.content_hash,
            # permission scope stored as comma-joined string for filterability
            "permission_scope": ",".join(self.permission_scope),
            "page": -1 if self.page is None else self.page,
            "section": self.section or "",
            "sequence": self.sequence,
        }


class RetrievalResult(AutoFlowModel):
    """One retrieved, authorized chunk with normalized scoring + provenance."""

    chunk_id: str
    document_id: str
    text: str
    raw_score: float
    normalized_score: float = Field(ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)
    page: int | None = None
    source_id: str | None = None
    file_name: str | None = None


class Evidence(AutoFlowModel):
    """A citation-ready evidence record. Never fabricated."""

    evidence_id: str
    document_id: str
    chunk_id: str
    source: str | None = None
    page: int | None = None
    snippet: str = ""
    score: float = 0.0

    @classmethod
    def from_result(cls, result: RetrievalResult, index: int) -> "Evidence":
        return cls(
            evidence_id=f"ev_{index:03d}",
            document_id=result.document_id,
            chunk_id=result.chunk_id,
            source=result.file_name,
            page=result.page,
            snippet=result.text[:280],
            score=round(result.normalized_score, 4),
        )


class SearchResponse(AutoFlowModel):
    """Full result of a knowledge search."""

    status: RetrievalStatus
    results: tuple[RetrievalResult, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    considered: int = 0
    authorized: int = 0
    deduplicated: int = 0
    query_latency_ms: int | None = None
    detail: str | None = None
