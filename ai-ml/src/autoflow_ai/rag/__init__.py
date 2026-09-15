"""RAG: local knowledge ingestion + embeddings + ChromaDB + authorized
semantic retrieval + evidence.

Design invariant: ChromaDB is storage/retrieval, NOT authorization. Similarity
is never permission. The retrieval pipeline always authorizes (physical
metadata filter) BEFORE returning results, and retrieved content enters the
context engine as AUTHORIZED_KNOWLEDGE data — never as instructions.
"""

from __future__ import annotations

from .errors import (
    RagError,
    IngestionError,
    EmbeddingError,
    StoreError,
    UnsupportedDocument,
    PathSecurityError,
)
from .models import (
    Chunk,
    Document,
    DocumentVersion,
    Evidence,
    RetrievalResult,
    RetrievalStatus,
    SearchResponse,
)
from .config import RagConfig, load_rag_config
from .embeddings import EmbeddingProvider, LocalHashingEmbedder, build_embedder
from .service import KnowledgeService, build_knowledge_service

__all__ = [
    "RagError",
    "IngestionError",
    "EmbeddingError",
    "StoreError",
    "UnsupportedDocument",
    "PathSecurityError",
    "Chunk",
    "Document",
    "DocumentVersion",
    "Evidence",
    "RetrievalResult",
    "RetrievalStatus",
    "SearchResponse",
    "RagConfig",
    "load_rag_config",
    "EmbeddingProvider",
    "LocalHashingEmbedder",
    "build_embedder",
    "KnowledgeService",
    "build_knowledge_service",
]
