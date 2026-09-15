"""RAG error types (controlled failures, never silent)."""

from __future__ import annotations


class RagError(Exception):
    """Base class for all RAG errors."""


class IngestionError(RagError):
    """A document could not be ingested."""


class EmbeddingError(RagError):
    """Embedding generation failed (no partial/fake vectors are written)."""


class StoreError(RagError):
    """The vector store failed (unavailable, corrupt, query/write failure)."""


class UnsupportedDocument(IngestionError):
    """The document type is not supported."""


class PathSecurityError(IngestionError):
    """An ingestion path violated the configured security policy."""
