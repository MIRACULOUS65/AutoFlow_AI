"""Embedding providers.

Two real implementations behind one interface:

* LocalHashingEmbedder — deterministic, offline, no dependencies. It produces
  real, stable vectors from token hashing (a bag-of-hashed-words model). It is
  NOT semantically strong, and is honestly labelled as a deterministic baseline.
  It exists so the whole RAG pipeline runs offline and tests are hermetic.

* RemoteEmbedder — calls an OpenAI-compatible ``/embeddings`` endpoint
  (NVIDIA NIM, ModelScope, OpenAI, etc.). Real semantic embeddings. Credentials
  come from config and are never logged or embedded in vectors.

Determinism: for a fixed embedder + fixed input, the same vector is returned.
Embeddings from different models must never be mixed in one collection (the
store records the embedder signature to guard against this).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable

from .config import RagConfig
from .errors import EmbeddingError

_WORD_RE = re.compile(r"[a-z0-9]+")


@runtime_checkable
class EmbeddingProvider(Protocol):
    provider_name: str
    model_id: str
    dimension: int

    def embed_text(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def health(self) -> bool: ...

    def signature(self) -> str:
        """Stable identifier of (provider, model, dimension) for mix-guarding."""
        ...


class LocalHashingEmbedder:
    """Deterministic hashing embedder (offline baseline, real vectors)."""

    provider_name = "local"

    def __init__(self, *, dimension: int = 384, model_id: str = "hash-v1") -> None:
        if dimension <= 0:
            raise EmbeddingError("dimension must be > 0")
        self.dimension = dimension
        self.model_id = model_id

    def _tokens(self, text: str) -> list[str]:
        return _WORD_RE.findall(text.lower())

    def embed_text(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        tokens = self._tokens(text)
        if not tokens:
            # deterministic non-zero vector for empty text
            vec[0] = 1.0
            return vec
        for tok in tokens:
            h = hashlib.sha256(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % self.dimension
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign
        # L2 normalize for cosine space
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]

    def health(self) -> bool:
        return True

    def signature(self) -> str:
        return f"{self.provider_name}:{self.model_id}:{self.dimension}"


class RemoteEmbedder:
    """OpenAI-compatible /embeddings adapter (real semantic embeddings)."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model_id: str,
        dimension: int,
        timeout_seconds: float = 60.0,
        transport=None,
    ) -> None:
        if not base_url:
            raise EmbeddingError("EMBEDDING_BASE_URL required for remote embedder")
        if not model_id:
            raise EmbeddingError("EMBEDDING_MODEL required for remote embedder")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model_id = model_id
        self.dimension = dimension
        self._timeout = timeout_seconds
        self._transport = transport or _urllib_transport

    def _post(self, texts: list[str]) -> list[list[float]]:
        url = f"{self._base_url}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body = json.dumps({"model": self.model_id, "input": texts}).encode("utf-8")
        status, text = self._transport(url, headers, body, self._timeout)
        if status >= 400:
            raise EmbeddingError(f"embedding endpoint error (HTTP {status})")
        try:
            data = json.loads(text)
            vectors = [row["embedding"] for row in data["data"]]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise EmbeddingError(f"malformed embedding response: {exc}") from exc
        if len(vectors) != len(texts):
            raise EmbeddingError("embedding count mismatch")
        return vectors

    def embed_text(self, text: str) -> list[float]:
        return self._post([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._post(texts)

    def health(self) -> bool:
        try:
            self.embed_text("health check")
            return True
        except EmbeddingError:
            return False

    def signature(self) -> str:
        return f"{self.provider_name}:{self.model_id}:{self.dimension}"


def _urllib_transport(url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:  # pragma: no cover - network
        raise EmbeddingError(f"embedding connection error: {getattr(exc,'reason',exc)}") from exc


def build_embedder(config: RagConfig, *, transport=None) -> EmbeddingProvider:
    """Construct the embedder from config. Falls back to local on missing
    remote config so the pipeline always runs."""

    if config.embedding_provider == "openai_compatible" and config.embedding_base_url and config.embedding_model:
        return RemoteEmbedder(
            base_url=config.embedding_base_url,
            api_key=config.embedding_api_key,
            model_id=config.embedding_model,
            dimension=config.embedding_dimension,
            transport=transport,
        )
    return LocalHashingEmbedder(dimension=config.embedding_dimension)
