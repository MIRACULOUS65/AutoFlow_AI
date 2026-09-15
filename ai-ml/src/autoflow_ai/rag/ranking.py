"""Score normalization and reranker interface.

Chroma cosine distance: smaller = closer. We normalize to [0,1] where higher is
more relevant. The Reranker interface is deterministic for now (identity order)
but leaves room for cross-encoder/LLM rerankers later without a second model.
"""

from __future__ import annotations

from typing import Protocol

from .models import RetrievalResult


def normalize_cosine_distance(distance: float) -> float:
    """Map cosine distance (0..2) to relevance (1..0), clamped to [0,1]."""

    rel = 1.0 - (distance / 2.0)
    return max(0.0, min(1.0, rel))


class Reranker(Protocol):
    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]: ...


class IdentityReranker:
    """Deterministic pass-through reranker (keeps score order)."""

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        return sorted(results, key=lambda r: (-r.normalized_score, r.chunk_id))
