"""KnowledgeService — the high-level RAG API.

Hides Chroma/embeddings/chunking behind ingest/search/get/delete/reindex/health.
Enforces path security, size limits, ingestion idempotency and versioning, and
never reports a document as indexed if embedding/storage failed.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from .chroma_store import ChromaStore
from .chunking import DeterministicChunker
from .config import RagConfig, load_rag_config
from .embeddings import EmbeddingProvider, build_embedder
from .errors import EmbeddingError, IngestionError, PathSecurityError, StoreError
from .filters import KnowledgeAuthorizationFilter, KnowledgeIdentity
from .loaders import MIME_BY_SUFFIX, SUPPORTED_SUFFIXES, load_blocks
from .models import Chunk, Document, RetrievalStatus, SearchResponse
from .retriever import Retriever


@dataclass
class IngestResult:
    document_id: str
    version: int
    chunks: int
    reused: bool  # True if identical content was already ingested
    status: str = "indexed"
    metrics: dict = field(default_factory=dict)


def _doc_id(tenant: str, workspace: str, file_name: str) -> str:
    raw = f"{tenant}/{workspace}/{file_name}"
    return "doc_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


class KnowledgeService:
    def __init__(
        self,
        *,
        config: RagConfig,
        store: ChromaStore,
        embedder: EmbeddingProvider,
        allowed_roots: list[Path] | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._embedder = embedder
        self._chunker = DeterministicChunker(
            chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap
        )
        self._retriever = Retriever(
            store=store,
            embedder=embedder,
            min_score=config.min_score,
            max_top_k=config.max_top_k,
        )
        self._allowed_roots = [r.resolve() for r in (allowed_roots or [])]
        # in-memory version ledger (backend persists this later)
        self._versions: dict[str, str] = {}  # document_id -> content_hash

    # -- path security -------------------------------------------------------

    def _check_path(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.exists():
            raise IngestionError(f"file does not exist: {path}")
        if not resolved.is_file():
            raise IngestionError(f"not a file: {path}")
        if self._allowed_roots:
            if not any(
                str(resolved).startswith(str(root)) for root in self._allowed_roots
            ):
                raise PathSecurityError(f"path outside allowed ingestion roots: {path}")
        size_mb = resolved.stat().st_size / (1024 * 1024)
        if size_mb > self._config.max_document_size_mb:
            raise IngestionError(
                f"document exceeds max size {self._config.max_document_size_mb}MB: {size_mb:.1f}MB"
            )
        if resolved.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise IngestionError(f"unsupported document type: {resolved.suffix!r}")
        return resolved

    # -- ingest --------------------------------------------------------------

    def ingest(
        self,
        path: str | Path,
        *,
        tenant_id: str,
        workspace_id: str,
        permission_scope: tuple[str, ...] = (),
        source_type: str = "file",
    ) -> IngestResult:
        t0 = time.perf_counter()
        resolved = self._check_path(Path(path))
        file_name = resolved.name
        document_id = _doc_id(tenant_id, workspace_id, file_name)
        content_hash = _sha_file(resolved)

        # idempotency: identical content already ingested -> reuse
        if self._versions.get(document_id) == content_hash:
            return IngestResult(
                document_id=document_id,
                version=1,
                chunks=0,
                reused=True,
                status="reused",
            )

        version = 2 if document_id in self._versions else 1

        # parse
        blocks, page_count = load_blocks(resolved)
        raw_chunks = self._chunker.chunk(blocks)
        if len(raw_chunks) > self._config.max_chunks_per_document:
            raise IngestionError(
                f"document produced {len(raw_chunks)} chunks (>{self._config.max_chunks_per_document})"
            )
        if not raw_chunks:
            raise IngestionError("document produced no chunks")

        chunks: list[Chunk] = []
        for i, rc in enumerate(raw_chunks):
            chunks.append(
                Chunk(
                    chunk_id=f"{document_id}:v{version}:{i}",
                    document_id=document_id,
                    version=version,
                    text=rc["text"],
                    sequence=rc["sequence"],
                    token_estimate=rc["token_estimate"],
                    content_hash=rc["content_hash"],
                    page=rc["page"],
                    section=rc["section"],
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    source_id=str(resolved),
                    source_type=source_type,
                    file_name=file_name,
                    permission_scope=permission_scope,
                )
            )

        # embed (fail before writing anything if embedding fails)
        try:
            embeddings = self._embedder.embed_documents([c.text for c in chunks])
        except EmbeddingError:
            raise
        if len(embeddings) != len(chunks):
            raise EmbeddingError("embedding/chunk count mismatch; ingestion aborted")

        # replace prior version, then upsert (store failure => not indexed)
        if version > 1:
            self._store.delete_document(document_id)
        self._store.upsert(chunks, embeddings)
        self._versions[document_id] = content_hash

        return IngestResult(
            document_id=document_id,
            version=version,
            chunks=len(chunks),
            reused=False,
            status="indexed",
            metrics={
                "ingest_ms": int((time.perf_counter() - t0) * 1000),
                "chunk_count": len(chunks),
                "page_count": page_count,
            },
        )

    # -- search --------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        workspace_id: str,
        permissions: frozenset[str] = frozenset(),
        top_k: int | None = None,
    ) -> SearchResponse:
        identity = KnowledgeIdentity(
            tenant_id=tenant_id, workspace_id=workspace_id, permissions=permissions
        )
        effective_top_k = self._config.top_k if top_k is None else top_k
        if effective_top_k <= 0:
            raise ValueError("top_k must be > 0")
        return self._retriever.search(query, identity=identity, top_k=effective_top_k)

    # -- management ----------------------------------------------------------

    def get_document(self, document_id: str) -> dict:
        return self._store.get_document_chunks(document_id)

    def delete_document(self, document_id: str) -> None:
        self._store.delete_document(document_id)
        self._versions.pop(document_id, None)

    def reindex(self, path: str | Path, **kwargs) -> IngestResult:
        # force a fresh version by clearing the ledger entry first
        resolved = Path(path).resolve()
        document_id = _doc_id(
            kwargs.get("tenant_id", ""), kwargs.get("workspace_id", ""), resolved.name
        )
        self._versions.pop(document_id, None)
        self._store.delete_document(document_id)
        return self.ingest(path, **kwargs)

    def health(self) -> dict:
        return {
            "store": self._store.health(),
            "embedder": self._embedder.health(),
            "embedder_signature": self._embedder.signature(),
            "collection": self._config.collection,
        }


def build_knowledge_service(
    *,
    config: RagConfig | None = None,
    chroma_path_override: str | None = None,
    embedder: EmbeddingProvider | None = None,
    allowed_roots: list[Path] | None = None,
    transport=None,
) -> KnowledgeService:
    cfg = config or load_rag_config(chroma_path_override=chroma_path_override)
    emb = embedder or build_embedder(cfg, transport=transport)
    store = ChromaStore(
        path=cfg.chroma_path,
        collection=cfg.collection,
        embedder_signature=emb.signature(),
    )
    return KnowledgeService(
        config=cfg, store=store, embedder=emb, allowed_roots=allowed_roots
    )
