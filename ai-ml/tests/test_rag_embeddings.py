"""Embedding provider tests (local determinism + remote adapter via transport)."""

from __future__ import annotations

import json

import pytest

from autoflow_ai.rag.embeddings import (
    LocalHashingEmbedder,
    RemoteEmbedder,
    build_embedder,
)
from autoflow_ai.rag.config import RagConfig
from autoflow_ai.rag.errors import EmbeddingError

pytestmark = pytest.mark.unit


def _cfg(**o):
    base = dict(
        enabled=True, top_k=8, max_top_k=20, chunk_size=800, chunk_overlap=120,
        min_score=0.0, rerank_enabled=False, chroma_path="./x", collection="c",
        max_document_size_mb=25, max_chunks_per_document=5000,
        embedding_provider="local", embedding_model="", embedding_base_url=None,
        embedding_api_key=None, embedding_dimension=384, embedding_batch_size=32,
    )
    base.update(o)
    return RagConfig(**base)


def test_local_embedder_deterministic_and_normalized():
    e = LocalHashingEmbedder(dimension=128)
    v1 = e.embed_text("hello world")
    v2 = e.embed_text("hello world")
    assert v1 == v2
    # L2 norm ~ 1
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_local_embedder_different_text_differs():
    e = LocalHashingEmbedder(dimension=128)
    assert e.embed_text("alpha") != e.embed_text("beta")


def test_local_embedder_signature():
    e = LocalHashingEmbedder(dimension=64, model_id="hash-v1")
    assert e.signature() == "local:hash-v1:64"


def test_build_embedder_defaults_to_local_without_remote_config():
    e = build_embedder(_cfg(embedding_provider="openai_compatible"))  # no base_url/model
    assert isinstance(e, LocalHashingEmbedder)


def test_build_embedder_uses_remote_when_configured():
    e = build_embedder(
        _cfg(
            embedding_provider="openai_compatible",
            embedding_base_url="https://api.example.com/v1",
            embedding_model="test-embed",
        ),
        transport=lambda url, headers, body, timeout: (200, json.dumps({"data": [{"embedding": [0.1, 0.2, 0.3]}]})),
    )
    assert isinstance(e, RemoteEmbedder)


def test_remote_embedder_parses_response():
    def transport(url, headers, body, timeout):
        payload = json.loads(body)
        vecs = [{"embedding": [0.1, 0.2, 0.3, 0.4]} for _ in payload["input"]]
        return 200, json.dumps({"data": vecs})

    e = RemoteEmbedder(
        base_url="https://api.example.com/v1",
        api_key="k",
        model_id="test-embed",
        dimension=4,
        transport=transport,
    )
    assert e.embed_text("x") == [0.1, 0.2, 0.3, 0.4]
    assert len(e.embed_documents(["a", "b"])) == 2


def test_remote_embedder_sends_auth_header():
    seen = {}

    def transport(url, headers, body, timeout):
        seen.update(headers)
        return 200, json.dumps({"data": [{"embedding": [0.1]}]})

    RemoteEmbedder(base_url="https://x/v1", api_key="secret", model_id="m", dimension=1, transport=transport).embed_text("x")
    assert seen.get("Authorization") == "Bearer secret"


def test_remote_embedder_http_error():
    e = RemoteEmbedder(
        base_url="https://x/v1", api_key="k", model_id="m", dimension=3,
        transport=lambda *a: (500, "boom"),
    )
    with pytest.raises(EmbeddingError):
        e.embed_text("x")


def test_remote_embedder_malformed_response():
    e = RemoteEmbedder(
        base_url="https://x/v1", api_key="k", model_id="m", dimension=3,
        transport=lambda *a: (200, "not json"),
    )
    with pytest.raises(EmbeddingError):
        e.embed_text("x")


def test_remote_embedder_requires_base_and_model():
    with pytest.raises(EmbeddingError):
        RemoteEmbedder(base_url="", api_key=None, model_id="m", dimension=3)
    with pytest.raises(EmbeddingError):
        RemoteEmbedder(base_url="https://x", api_key=None, model_id="", dimension=3)
