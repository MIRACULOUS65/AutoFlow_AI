"""Persistent ChromaDB store behind a small interface.

We pass our own embeddings (never Chroma's default embedder), so no onnxruntime
dependency is required. Authorization is enforced by physical ``where`` metadata
filters — similarity is never permission. The embedder signature is recorded so
vectors from different embedding models are never mixed in one collection.
"""

from __future__ import annotations

from pathlib import Path

from .errors import StoreError
from .models import Chunk


class ChromaStore:
    def __init__(self, *, path: str, collection: str, embedder_signature: str) -> None:
        self._path = path
        self._collection_name = collection
        self._sig = embedder_signature
        self._client = None
        self._collection = None

    # -- lifecycle -----------------------------------------------------------

    def _connect(self):
        if self._collection is not None:
            return
        try:
            import chromadb
            from chromadb.config import Settings
        except Exception as exc:  # pragma: no cover
            raise StoreError(f"chromadb unavailable: {exc}") from exc
        try:
            Path(self._path).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self._path,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine", "embedder": self._sig},
            )
        except Exception as exc:
            raise StoreError(f"failed to open collection: {exc}") from exc
        self._guard_embedder_mix()

    def _guard_embedder_mix(self) -> None:
        existing = (self._collection.metadata or {}).get("embedder")
        if existing and existing != self._sig:
            raise StoreError(
                f"embedder mismatch: collection built with {existing!r}, "
                f"current embedder is {self._sig!r}"
            )

    # -- operations ----------------------------------------------------------

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise StoreError("chunk/embedding count mismatch")
        if not chunks:
            return
        self._connect()
        try:
            self._collection.upsert(
                ids=[c.chunk_id for c in chunks],
                embeddings=embeddings,
                documents=[c.text for c in chunks],
                metadatas=[c.store_metadata() for c in chunks],
            )
        except Exception as exc:
            raise StoreError(f"upsert failed: {exc}") from exc

    def query(self, embedding: list[float], *, top_k: int, where: dict | None = None):
        self._connect()
        try:
            return self._collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=where or None,
            )
        except Exception as exc:
            raise StoreError(f"query failed: {exc}") from exc

    def delete_document(self, document_id: str) -> None:
        self._connect()
        try:
            self._collection.delete(where={"document_id": document_id})
        except Exception as exc:
            raise StoreError(f"delete failed: {exc}") from exc

    def delete_version(self, document_id: str, version: int) -> None:
        self._connect()
        try:
            self._collection.delete(
                where={"$and": [{"document_id": document_id}, {"version": version}]}
            )
        except Exception as exc:
            raise StoreError(f"delete version failed: {exc}") from exc

    def count(self) -> int:
        self._connect()
        try:
            return self._collection.count()
        except Exception as exc:
            raise StoreError(f"count failed: {exc}") from exc

    def get_document_chunks(self, document_id: str) -> dict:
        self._connect()
        try:
            return self._collection.get(where={"document_id": document_id})
        except Exception as exc:
            raise StoreError(f"get failed: {exc}") from exc

    def health(self) -> bool:
        try:
            self._connect()
            self._collection.count()
            return True
        except StoreError:
            return False

    def reset_dev_only(self) -> None:
        """Explicit dev-only reset (not exposed to production paths)."""

        self._connect()
        try:
            self._client.reset()
            self._collection = None
        except Exception as exc:
            raise StoreError(f"reset failed: {exc}") from exc
