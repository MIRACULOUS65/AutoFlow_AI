"""Tests for the OpenAI-compatible HTTP provider.

Uses a real in-process http.server on localhost (exercises actual urllib
transport) plus an injected fake transport for failure-mode coverage. No
external network is used.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from autoflow_ai.model_gateway.http_provider import (
    AuthenticationError,
    OpenAICompatibleProvider,
)
from autoflow_ai.model_gateway.local_provider import default_local_model
from autoflow_ai.model_gateway.provider import ProviderError, ProviderTimeout
from autoflow_ai.schemas.enums import DeploymentType, ModelRole
from autoflow_ai.schemas.models import ModelCapability, ModelDefinition, ModelRequest

pytestmark = pytest.mark.integration


def _model() -> ModelDefinition:
    return ModelDefinition(
        model_id="model_http01",
        provider="openai_compatible",
        provider_model_name="test-model",
        display_name="Test",
        roles=(ModelRole.PLANNER,),
        capabilities=ModelCapability(text=True, structured_output=True, reasoning=True),
        context_window=8000,
        max_output_tokens=1024,
        deployment=DeploymentType.OPENAI_COMPATIBLE,
    )


def _request(structured: bool = False) -> ModelRequest:
    return ModelRequest(
        request_id="mreq_http",
        required_role=ModelRole.PLANNER,
        require_structured_output=structured,
    )


# ---- real local server ------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    reply_content = '{"result": "ok"}'
    require_auth = False

    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        # Always drain the request body first, otherwise closing the socket
        # early aborts the client connection on Windows (WinError 10053).
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        if self._Handler_flags().get("require_auth") and "Authorization" not in self.headers:
            payload = b'{"error":"unauthorized"}'
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        body = json.dumps(
            {
                "choices": [
                    {"message": {"content": self._Handler_flags()["reply"]}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _Handler_flags():
        return _SERVER_FLAGS


_SERVER_FLAGS = {"reply": "hello world", "require_auth": False}


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


def test_real_server_text_response(server):
    _SERVER_FLAGS["reply"] = "the plan is ready"
    _SERVER_FLAGS["require_auth"] = False
    provider = OpenAICompatibleProvider(base_url=server, api_key=None)
    resp = provider.generate(_model(), _request(), "plan this")
    assert resp.text == "the plan is ready"
    assert resp.provider == "openai_compatible"
    assert resp.usage.input_tokens == 5


def test_real_server_structured_response(server):
    _SERVER_FLAGS["reply"] = '{"goal": "edit doc"}'
    _SERVER_FLAGS["require_auth"] = False
    provider = OpenAICompatibleProvider(base_url=server, api_key="k")
    resp = provider.generate(_model(), _request(structured=True), "plan")
    assert resp.structured_output == {"goal": "edit doc"}


def test_real_server_auth_required(server):
    _SERVER_FLAGS["require_auth"] = True
    provider = OpenAICompatibleProvider(base_url=server, api_key=None)
    with pytest.raises(AuthenticationError):
        provider.generate(_model(), _request(), "x")
    _SERVER_FLAGS["require_auth"] = False


# ---- injected transport (failure modes) ------------------------------------


def _transport_returning(status, text):
    def _t(url, headers, body, timeout):
        return status, text
    return _t


def test_auth_failure_maps_to_auth_error():
    provider = OpenAICompatibleProvider(
        base_url="http://x", api_key="bad", transport=_transport_returning(401, "{}")
    )
    with pytest.raises(AuthenticationError):
        provider.generate(_model(), _request(), "x")


def test_server_error_maps_to_provider_error():
    provider = OpenAICompatibleProvider(
        base_url="http://x", api_key="k", transport=_transport_returning(500, "boom")
    )
    with pytest.raises(ProviderError):
        provider.generate(_model(), _request(), "x")


def test_timeout_status_maps_to_timeout():
    provider = OpenAICompatibleProvider(
        base_url="http://x", api_key="k", transport=_transport_returning(504, "{}")
    )
    with pytest.raises(ProviderTimeout):
        provider.generate(_model(), _request(), "x")


def test_malformed_json_maps_to_provider_error():
    provider = OpenAICompatibleProvider(
        base_url="http://x", api_key="k", transport=_transport_returning(200, "not json")
    )
    with pytest.raises(ProviderError):
        provider.generate(_model(), _request(), "x")


def test_unexpected_shape_maps_to_provider_error():
    provider = OpenAICompatibleProvider(
        base_url="http://x", api_key="k", transport=_transport_returning(200, '{"nope": true}')
    )
    with pytest.raises(ProviderError):
        provider.generate(_model(), _request(), "x")


def test_auth_error_is_non_retryable():
    from autoflow_ai.model_gateway.policies import RetryPolicy

    assert not RetryPolicy.is_retryable(AuthenticationError("no"))


def test_base_url_required():
    with pytest.raises(ValueError):
        OpenAICompatibleProvider(base_url="", api_key=None)


def test_provider_does_not_support_local_model():
    provider = OpenAICompatibleProvider(base_url="http://x", api_key=None)
    assert not provider.supports(default_local_model())
