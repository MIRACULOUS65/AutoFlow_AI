"""Tests for streaming (SSE) support in the OpenAI-compatible provider."""

from __future__ import annotations

import pytest

from autoflow_ai.model_gateway.http_provider import (
    AuthenticationError,
    OpenAICompatibleProvider,
)
from autoflow_ai.model_gateway.provider import ProviderError, ProviderTimeout
from autoflow_ai.schemas.enums import DeploymentType, ModelRole
from autoflow_ai.schemas.models import ModelCapability, ModelDefinition, ModelRequest

pytestmark = pytest.mark.integration


def _model(streaming: bool = True) -> ModelDefinition:
    return ModelDefinition(
        model_id="model_stream01",
        provider="openai_compatible",
        provider_model_name="reasoner-1",
        display_name="Reasoner",
        roles=(ModelRole.PLANNER,),
        capabilities=ModelCapability(text=True, structured_output=True, reasoning=True, streaming=streaming),
        context_window=8000,
        max_output_tokens=512,
        deployment=DeploymentType.OPENAI_COMPATIBLE,
        requires_streaming=streaming,
    )


def _req(structured: bool = False) -> ModelRequest:
    return ModelRequest(
        request_id="mreq_s", required_role=ModelRole.PLANNER, require_structured_output=structured
    )


def _sse(*chunks: str):
    """Build an SSE line iterator from raw data payloads."""

    lines = [f"data: {c}" for c in chunks] + ["data: [DONE]"]

    def _transport(url, headers, body, timeout):
        return 200, iter(lines)

    return _transport


def test_streaming_aggregates_content():
    st = _sse(
        '{"choices":[{"delta":{"content":"Hello"}}]}',
        '{"choices":[{"delta":{"content":" world"}}]}',
        '{"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
    )
    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k", stream_transport=st)
    resp = provider.generate(_model(), _req(), "hi")
    assert resp.text == "Hello world"
    assert resp.finish_reason == "stop"
    assert resp.usage.output_tokens == 2


def test_streaming_discards_reasoning_content():
    st = _sse(
        '{"choices":[{"delta":{"reasoning_content":"let me think..."}}]}',
        '{"choices":[{"delta":{"reasoning_content":"more thinking"}}]}',
        '{"choices":[{"delta":{"content":"final answer"}}]}',
    )
    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k", stream_transport=st)
    resp = provider.generate(_model(), _req(), "hi")
    assert resp.text == "final answer"
    assert "think" not in (resp.text or "")


def test_streaming_structured_output():
    st = _sse(
        '{"choices":[{"delta":{"content":"{\\"goal\\":"}}]}',
        '{"choices":[{"delta":{"content":" \\"edit\\"}"}}]}',
    )
    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k", stream_transport=st)
    resp = provider.generate(_model(), _req(structured=True), "plan")
    assert resp.structured_output == {"goal": "edit"}


def test_streaming_empty_stream_errors():
    def st(url, headers, body, timeout):
        return 200, iter(())

    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k", stream_transport=st)
    with pytest.raises(ProviderError, match="empty streaming"):
        provider.generate(_model(), _req(), "hi")


def test_streaming_no_content_errors():
    st = _sse('{"choices":[{"delta":{"reasoning_content":"only thinking"}}]}')
    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k", stream_transport=st)
    with pytest.raises(ProviderError, match="no content"):
        provider.generate(_model(), _req(), "hi")


def test_streaming_auth_error():
    def st(url, headers, body, timeout):
        return 401, iter(())

    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="bad", stream_transport=st)
    with pytest.raises(AuthenticationError):
        provider.generate(_model(), _req(), "hi")


def test_streaming_server_error():
    def st(url, headers, body, timeout):
        return 500, iter(())

    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k", stream_transport=st)
    with pytest.raises(ProviderError):
        provider.generate(_model(), _req(), "hi")


def test_non_streaming_model_uses_regular_path():
    import json

    def transport(url, headers, body, timeout):
        # assert we did NOT request streaming
        assert json.loads(body)["stream"] is False
        return 200, json.dumps(
            {"choices": [{"message": {"content": "plain"}, "finish_reason": "stop"}], "usage": {}}
        )

    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k", transport=transport)
    resp = provider.generate(_model(streaming=False), _req(), "hi")
    assert resp.text == "plain"


def test_streaming_model_sets_stream_flag():
    import json

    seen = {}

    def st(url, headers, body, timeout):
        seen["body"] = json.loads(body)
        return 200, iter(['data: {"choices":[{"delta":{"content":"x"}}]}', "data: [DONE]"])

    provider = OpenAICompatibleProvider(base_url="http://x/v1", api_key="k", stream_transport=st)
    provider.generate(_model(streaming=True), _req(), "hi")
    assert seen["body"]["stream"] is True
