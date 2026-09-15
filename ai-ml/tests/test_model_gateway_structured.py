"""Tests for structured-output parsing and policies."""

from __future__ import annotations

import pytest

from autoflow_ai.model_gateway.policies import ProviderHealth, RetryPolicy
from autoflow_ai.model_gateway.provider import ProviderError, ProviderTimeout
from autoflow_ai.model_gateway.structured import (
    StructuredOutputError,
    extract_json,
    parse_into,
)
from autoflow_ai.schemas.agents import ProposedAction
from autoflow_ai.schemas.enums import ActionType

pytestmark = pytest.mark.unit


def test_extract_direct_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    text = "Here is the plan:\n```json\n{\"step\": 1}\n```\nDone."
    assert extract_json(text) == {"step": 1}


def test_extract_json_from_prose_braces():
    text = "sure! {\"ok\": true} hope that helps"
    assert extract_json(text) == {"ok": True}


def test_extract_json_invalid_raises():
    with pytest.raises(StructuredOutputError):
        extract_json("no json at all here")


def test_extract_json_broken_braces_raises():
    with pytest.raises(StructuredOutputError):
        extract_json("{not valid json}")


def test_parse_into_validates_model():
    text = '{"action_type": "tool_call", "tool": "email.send", "reason": "send it", "confidence": 0.9}'
    action = parse_into(text, ProposedAction)
    assert action.action_type == ActionType.TOOL_CALL
    assert action.tool == "email.send"


def test_parse_into_rejects_bad_shape():
    # tool_call without a tool is invalid per ProposedAction rules
    text = '{"action_type": "tool_call", "reason": "x", "confidence": 0.5}'
    with pytest.raises(StructuredOutputError):
        parse_into(text, ProposedAction)


# -- policies ----------------------------------------------------------------


def test_retry_policy_requires_positive_attempts():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)


def test_retry_policy_backoff():
    rp = RetryPolicy(max_attempts=3, base_delay_seconds=1.0, backoff_factor=2.0)
    assert rp.delay_for(1) == 1.0
    assert rp.delay_for(2) == 2.0
    assert rp.delay_for(3) == 4.0


def test_retryable_classification():
    assert RetryPolicy.is_retryable(ProviderTimeout("t"))
    assert RetryPolicy.is_retryable(ProviderError("generic"))

    class NonRetryable(ProviderError):
        non_retryable = True

    assert not RetryPolicy.is_retryable(NonRetryable("auth"))
    assert not RetryPolicy.is_retryable(ValueError("other"))


def test_provider_health_marks_unhealthy_after_failures():
    h = ProviderHealth()
    assert h.healthy
    for _ in range(3):
        h.record_failure("boom")
    assert not h.healthy
    assert h.failure_rate == 1.0
    h.record_success()
    assert h.healthy
    assert h.consecutive_failures == 0
