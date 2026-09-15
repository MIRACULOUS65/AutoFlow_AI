"""Retriever: authorized semantic search producing evidence.

Pipeline: authorize (physical where) -> chroma search -> python-side permission
check -> normalize scores -> dedupe -> rerank -> evidence. Distinguishes
NO_RESULTS from NO_AUTHORIZED_EVIDENCE.
"""

from __future__ import annotations

import time

from .chroma_store import ChromaStore
from .embeddings import EmbeddingProvider
from .errors import StoreError
from .filters import KnowledgeAuthorizationFilter, KnowledgeIdentity
from .models import Evidence, RetrievalResult, RetrievalStatus, SearchResponse
from .ranking import IdentityReranker, Reranker, normalize_cosine_distance


class Retriever:
    def __init__(
        self,
        *,
        store: ChromaStore,
        embedder: EmbeddingProvider,
        authorizer: KnowledgeAuthorizationFilter | None = None,
        reranker: Reranker | None = None,
        min_score: float = 0.0,
        max_top_k: int = 20,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._authorizer = authorizer or KnowledgeAuthorizationFilter()
        self._reranker = reranker or IdentityReranker()
        self._min_score = min_score
        self._max_top_k = max_top_k

    def search(
        self,
        query: str,
        *,
        identity: KnowledgeIdentity,
        top_k: int = 8,
    ) -> SearchResponse:
        if top_k <= 0:
            raise ValueError("top_k must be > 0")
        top_k = min(top_k, self._max_top_k)

        start = time.perf_counter()
        try:
            query_vec = self._embedder.embed_text(query)
            where = self._authorizer.where_clause(identity)
            # over-fetch a little so python-side permission filtering still fills top_k
            raw = self._store.query(query_vec, top_k=top_k * 3, where=where)
        except StoreError as exc:
            return SearchResponse(status=RetrievalStatus.FAILED, detail=str(exc))

        ids = (raw.get("ids") or [[]])[0]
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]
        considered = len(ids)

        if considered == 0:
            return SearchResponse(
                status=RetrievalStatus.NO_RESULTS,
                considered=0,
                query_latency_ms=int((time.perf_counter() - start) * 1000),
            )

        # python-side authorization + score normalization
        authorized: list[RetrievalResult] = []
        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            if not self._authorizer.permitted(meta, identity):
                continue
            norm = normalize_cosine_distance(float(dist))
            if norm < self._min_score:
                continue
            page = meta.get("page")
            authorized.append(
                RetrievalResult(
                    chunk_id=cid,
                    document_id=meta.get("document_id", ""),
                    text=doc,
                    raw_score=float(dist),
                    normalized_score=norm,
                    metadata=meta,
                    page=None if page in (None, -1) else int(page),
                    source_id=meta.get("source_id"),
                    file_name=meta.get("file_name"),
                )
            )

        if not authorized:
            return SearchResponse(
                status=RetrievalStatus.NO_AUTHORIZED_EVIDENCE,
                considered=considered,
                authorized=0,
                query_latency_ms=int((time.perf_counter() - start) * 1000),
            )

        # dedupe by content hash (keep highest score)
        deduped: dict[str, RetrievalResult] = {}
        dup_count = 0
        for r in sorted(authorized, key=lambda x: -x.normalized_score):
            key = r.metadata.get("content_hash", r.chunk_id)
            if key in deduped:
                dup_count += 1
            else:
                deduped[key] = r
        results = self._reranker.rerank(query, list(deduped.values()))[:top_k]

        evidence = tuple(Evidence.from_result(r, i + 1) for i, r in enumerate(results))
        return SearchResponse(
            status=RetrievalStatus.SUCCESS,
            results=tuple(results),
            evidence=evidence,
            considered=considered,
            authorized=len(authorized),
            deduplicated=dup_count,
            query_latency_ms=int((time.perf_counter() - start) * 1000),
        )
