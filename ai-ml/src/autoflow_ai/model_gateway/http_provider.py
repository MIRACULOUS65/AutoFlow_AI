"""OpenAI-compatible HTTP provider adapter.

Works with any endpoint exposing the OpenAI Chat Completions shape
(`POST {base_url}/chat/completions`): OpenAI, vLLM, LM Studio, Ollama's
OpenAI-compatible API, etc. Credentials come from configuration and are sent
only in the Authorization header — never logged, never placed in prompts.

Uses the standard library (urllib) so no new dependency is required and the
module imports without any network access. A pluggable ``transport`` callable
makes it fully testable against a local fake server.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable

from typing import Iterable

from ..schemas.models import ModelDefinition, ModelRequest, ModelResponse, ModelUsage
from .provider import ProviderError, ProviderTimeout

# transport(url, headers, body_bytes, timeout) -> (status_code, response_text)
Transport = Callable[[str, dict, bytes, float], tuple[int, str]]
# stream_transport(url, headers, body_bytes, timeout) -> (status_code, iterable_of_lines)
StreamTransport = Callable[[str, dict, bytes, float], tuple[int, Iterable[str]]]


class AuthenticationError(ProviderError):
    """Provider rejected the credentials (non-retryable)."""

    non_retryable = True


def _urllib_transport(url: str, headers: dict, body: bytes, timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - controlled url
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:  # non-2xx
        text = exc.read().decode("utf-8", errors="replace")
        return exc.code, text
    except TimeoutError as exc:  # pragma: no cover - real timeout
        raise ProviderTimeout(str(exc)) from exc
    except urllib.error.URLError as exc:  # pragma: no cover - real network
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            raise ProviderTimeout(str(reason)) from exc
        raise ProviderError(f"connection error: {reason}") from exc


def _urllib_stream_transport(url: str, headers: dict, body: bytes, timeout: float):
    """Open an SSE stream and return (status, line_iterator).

    On a non-2xx status the error body is returned as a single-line iterable so
    the caller's status handling still runs.
    """

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
    except urllib.error.HTTPError as exc:  # non-2xx
        return exc.code, iter(())
    except TimeoutError as exc:  # pragma: no cover
        raise ProviderTimeout(str(exc)) from exc
    except urllib.error.URLError as exc:  # pragma: no cover
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            raise ProviderTimeout(str(reason)) from exc
        raise ProviderError(f"connection error: {reason}") from exc

    def _lines():
        try:
            for chunk in resp:
                yield chunk.decode("utf-8", errors="replace")
        finally:
            resp.close()

    return resp.status, _lines()


class OpenAICompatibleProvider:
    """Provider adapter for OpenAI-style chat completion endpoints."""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        timeout_seconds: float = 60.0,
        transport: Transport | None = None,
        stream_transport: StreamTransport | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._transport = transport or _urllib_transport
        self._stream_transport = stream_transport or _urllib_stream_transport
        self._healthy = True

    def supports(self, model: ModelDefinition) -> bool:
        return model.provider == self.name

    def health(self) -> bool:
        return self._healthy

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _payload(self, model: ModelDefinition, request: ModelRequest, prompt: str, *, stream: bool) -> dict:
        payload: dict = {
            "model": model.provider_model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens
        if request.require_structured_output:
            # OpenAI-compatible JSON mode; harmless if the server ignores it.
            payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _raise_for_status(status: int) -> None:
        if status in (401, 403):
            raise AuthenticationError(f"authentication failed (HTTP {status})")
        if status in (408, 504):
            raise ProviderTimeout(f"provider timeout (HTTP {status})")
        if status >= 500:
            raise ProviderError(f"provider server error (HTTP {status})")
        if status >= 400:
            raise ProviderError(f"provider request error (HTTP {status})")

    def generate(
        self, model: ModelDefinition, request: ModelRequest, prompt: str
    ) -> ModelResponse:
        if model.requires_streaming:
            return self._generate_streaming(model, request, prompt)

        url = f"{self._base_url}/chat/completions"
        body = json.dumps(self._payload(model, request, prompt, stream=False)).encode("utf-8")
        status, text = self._transport(url, self._headers(), body, self._timeout)
        self._raise_for_status(status)
        return self._parse_response(model, request, text)

    def _generate_streaming(
        self, model: ModelDefinition, request: ModelRequest, prompt: str
    ) -> ModelResponse:
        """Aggregate an SSE stream into a single normalized ModelResponse.

        ``reasoning_content`` deltas are intentionally DISCARDED (no hidden
        chain-of-thought leaves the gateway). Only ``content`` is aggregated.
        """

        url = f"{self._base_url}/chat/completions"
        body = json.dumps(self._payload(model, request, prompt, stream=True)).encode("utf-8")
        status, lines = self._stream_transport(url, self._headers(), body, self._timeout)
        self._raise_for_status(status)

        content_parts: list[str] = []
        finish = "stop"
        usage_raw: dict = {}
        saw_any = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            saw_any = True
            choices = obj.get("choices") or []
            if choices:
                delta = choices[0].get("delta", {}) or {}
                piece = delta.get("content")
                if piece:
                    content_parts.append(piece)
                # reasoning_content is deliberately ignored
                if choices[0].get("finish_reason"):
                    finish = choices[0]["finish_reason"]
            if obj.get("usage"):
                usage_raw = obj["usage"]

        if not saw_any:
            raise ProviderError("empty streaming response")

        content = "".join(content_parts)
        if not content:
            raise ProviderError("streaming response produced no content")

        usage = ModelUsage(
            input_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
        )
        structured = None
        if request.require_structured_output:
            from .structured import StructuredOutputError, extract_json

            try:
                structured = extract_json(content)
            except StructuredOutputError as exc:
                raise ProviderError(f"structured output invalid: {exc}") from exc

        return ModelResponse(
            request_id=request.request_id,
            model_id=model.model_id,
            provider=self.name,
            finish_reason=finish or "stop",
            text=content if structured is None else None,
            structured_output=structured,
            usage=usage,
        )

    def _parse_response(
        self, model: ModelDefinition, request: ModelRequest, text: str
    ) -> ModelResponse:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"malformed provider response: {exc}") from exc

        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
            finish = choice.get("finish_reason", "stop")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected provider response shape: {exc}") from exc

        usage_raw = data.get("usage", {}) or {}
        usage = ModelUsage(
            input_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
        )

        structured = None
        if request.require_structured_output:
            from .structured import StructuredOutputError, extract_json

            try:
                structured = extract_json(content)
            except StructuredOutputError as exc:
                raise ProviderError(f"structured output invalid: {exc}") from exc

        return ModelResponse(
            request_id=request.request_id,
            model_id=model.model_id,
            provider=self.name,
            finish_reason=finish or "stop",
            text=content if structured is None else None,
            structured_output=structured,
            usage=usage,
        )
