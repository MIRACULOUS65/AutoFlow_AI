"""RAG configuration (environment-driven; secret-safe)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RagConfig:
    enabled: bool
    top_k: int
    max_top_k: int
    chunk_size: int
    chunk_overlap: int
    min_score: float
    rerank_enabled: bool
    chroma_path: str
    collection: str
    max_document_size_mb: float
    max_chunks_per_document: int

    # embeddings
    embedding_provider: str
    embedding_model: str
    embedding_base_url: str | None
    embedding_api_key: str | None = field(default=None, repr=False)
    embedding_dimension: int = 384
    embedding_batch_size: int = 32

    def redacted(self) -> dict:
        return {
            "enabled": self.enabled,
            "top_k": self.top_k,
            "max_top_k": self.max_top_k,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "min_score": self.min_score,
            "rerank_enabled": self.rerank_enabled,
            "chroma_path": self.chroma_path,
            "collection": self.collection,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_base_url": self.embedding_base_url,
            "embedding_api_key": "***set***" if self.embedding_api_key else None,
            "embedding_dimension": self.embedding_dimension,
        }


def _b(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def load_rag_config(*, chroma_path_override: str | None = None) -> RagConfig:
    return RagConfig(
        enabled=_b("RAG_ENABLED", "true"),
        top_k=int(os.environ.get("RAG_TOP_K", "8") or 8),
        max_top_k=int(os.environ.get("RAG_MAX_TOP_K", "20") or 20),
        chunk_size=int(os.environ.get("RAG_CHUNK_SIZE", "800") or 800),
        chunk_overlap=int(os.environ.get("RAG_CHUNK_OVERLAP", "120") or 120),
        min_score=float(os.environ.get("RAG_MIN_SCORE", "0.0") or 0.0),
        rerank_enabled=_b("RAG_RERANK_ENABLED", "false"),
        chroma_path=chroma_path_override or os.environ.get("CHROMA_PATH", "./data/chroma"),
        collection=os.environ.get("CHROMA_COLLECTION", "autoflow_knowledge"),
        max_document_size_mb=float(os.environ.get("MAX_DOCUMENT_SIZE_MB", "25") or 25),
        max_chunks_per_document=int(os.environ.get("MAX_CHUNKS_PER_DOCUMENT", "5000") or 5000),
        embedding_provider=os.environ.get("EMBEDDING_PROVIDER", "local").strip() or "local",
        embedding_model=os.environ.get("EMBEDDING_MODEL", "").strip(),
        embedding_base_url=os.environ.get("EMBEDDING_BASE_URL", "").strip() or None,
        embedding_api_key=os.environ.get("EMBEDDING_API_KEY", "").strip() or None,
        embedding_dimension=int(os.environ.get("EMBEDDING_DIMENSION", "384") or 384),
        embedding_batch_size=int(os.environ.get("EMBEDDING_BATCH_SIZE", "32") or 32),
    )
