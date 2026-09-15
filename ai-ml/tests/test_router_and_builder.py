"""Tests for router retry/fallback/health, gateway builder, and harness."""

from __future__ import annotations

import pytest

from autoflow_ai.model_gateway import (
    FallbackPolicy,
    LocalRuleProvider,
    ModelRegistry,
    ModelRouter,
    NoEligibleModel,
    ProviderError,
    RetryPolicy,
    build_gateway,
    run_harness,
    benchmark,
)
from autoflow_ai.model_gateway.config import GatewayConfig, ProviderConfig
from autoflow_ai.model_gateway.local_provider import default_local_model
from autoflow_ai.schemas.enums import DeploymentType, ModelRole
from autoflow_ai.schemas.models import (
    ModelCapability,
    ModelDefinition,
    ModelRequest,
    ModelResponse,
    ModelUsage,
)

pytestmark = pytest.mark.integration


def _req():
    return ModelRequest(
        request_id="mreq_r",
        required_role=ModelRole.PLANNER,
        required_capabilities={"structured_output": True},
    )


class _FlakyProvider:
    """Fails a set number of times, then succeeds."""

    name = "flaky"

    def __init__(self, fail_times: int, *, error=None):
        self.calls = 0
        self._fail_times = fail_times
        self._error = error or ProviderError("transient")

    def supports(self, model):
        return model.provider == "flaky"

    def health(self):
        return True

    def generate(self, model, request, prompt):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._error
        return ModelResponse(
            request_id=request.request_id,
            model_id=model.model_id,
            provider=self.name,
            finish_reason="stop",
            text="ok",
            usage=ModelUsage(input_tokens=1, output_tokens=1),
        )


def _flaky_model(model_id="model_flaky1", priority=100):
    return ModelDefinition(
        model_id=model_id,
        provider="flaky",
        provider_model_name="flaky-m",
        display_name="Flaky",
        roles=(ModelRole.PLANNER,),
        capabilities=ModelCapability(text=True, structured_output=True),
        context_window=8000,
        max_output_tokens=1024,
        deployment=DeploymentType.SELF_HOSTED,
        routing_priority=priority,
    )


def test_retry_succeeds_within_budget():
    reg = ModelRegistry()
    provider = _FlakyProvider(fail_times=1)
    reg.register(_flaky_model(), provider)
    router = ModelRouter(reg, retry_policy=RetryPolicy(max_attempts=2))
    resp = router.generate(_req(), "x")
    assert resp.text == "ok"
    assert provider.calls == 2  # one failure + one success


def test_retry_exhausts_then_fails():
    reg = ModelRegistry()
    provider = _FlakyProvider(fail_times=5)
    reg.register(_flaky_model(), provider)
    router = ModelRouter(
        reg, retry_policy=RetryPolicy(max_attempts=2), fallback_policy=FallbackPolicy(enabled=False)
    )
    with pytest.raises(NoEligibleModel):
        router.generate(_req(), "x")
    assert provider.calls == 2


def test_fallback_to_next_model():
    reg = ModelRegistry()
    always_fail = _FlakyProvider(fail_times=99)
    reg.register(_flaky_model("model_primary1", priority=200), always_fail)
    reg.register(default_local_model().model_copy(update={"routing_priority": 50}), LocalRuleProvider())
    router = ModelRouter(reg, retry_policy=RetryPolicy(max_attempts=1))
    resp = router.generate(_req(), "x")
    # fell back to local provider
    assert resp.provider == "local-rule"
    assert resp.is_fallback is True


def test_non_retryable_error_does_not_retry():
    class AuthErr(ProviderError):
        non_retryable = True

    reg = ModelRegistry()
    provider = _FlakyProvider(fail_times=99, error=AuthErr("bad key"))
    reg.register(_flaky_model(), provider)
    router = ModelRouter(
        reg, retry_policy=RetryPolicy(max_attempts=3), fallback_policy=FallbackPolicy(enabled=False)
    )
    with pytest.raises(NoEligibleModel):
        router.generate(_req(), "x")
    assert provider.calls == 1  # no retry on non-retryable


def test_health_tracks_failures():
    reg = ModelRegistry()
    provider = _FlakyProvider(fail_times=1)
    reg.register(_flaky_model(), provider)
    router = ModelRouter(reg, retry_policy=RetryPolicy(max_attempts=2))
    router.generate(_req(), "x")
    health = router.health_for("flaky")
    assert health.total_failures == 1
    assert health.total_calls >= 1


# -- builder ------------------------------------------------------------------


def test_builder_local_only_when_no_provider():
    cfg = GatewayConfig(providers=[], timeout_seconds=10, max_retries=1)
    reg, router = build_gateway(cfg)
    assert len(reg) == 1
    assert reg.models()[0].provider == "local-rule"


def test_builder_adds_http_provider_with_local_fallback():
    cfg = GatewayConfig(
        providers=[
            ProviderConfig(
                role_prefix="PRIMARY",
                provider="openai_compatible",
                model_id="gpt-test",
                base_url="http://127.0.0.1:9",
                context_window=16000,
                api_key="k",
            )
        ],
        timeout_seconds=10,
        max_retries=1,
    )

    def fake_transport(url, headers, body, timeout):
        import json

        return 200, json.dumps(
            {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}
        )

    reg, router = build_gateway(cfg, transport=fake_transport)
    providers = {m.provider for m in reg.models()}
    assert "openai_compatible" in providers
    assert "local-rule" in providers  # local kept as fallback
    resp = router.generate(_req(), "plan")
    assert resp.provider == "openai_compatible"  # real provider chosen first


def test_builder_skips_http_provider_without_base_url():
    cfg = GatewayConfig(
        providers=[
            ProviderConfig(
                role_prefix="PRIMARY",
                provider="openai_compatible",
                model_id="gpt-test",
                base_url=None,
                context_window=16000,
                api_key="k",
            )
        ],
        timeout_seconds=10,
        max_retries=1,
    )
    reg, _ = build_gateway(cfg)
    assert {m.provider for m in reg.models()} == {"local-rule"}


# -- harness ------------------------------------------------------------------


def test_harness_passes_on_local_gateway():
    cfg = GatewayConfig(providers=[], timeout_seconds=10, max_retries=1)
    _reg, router = build_gateway(cfg)
    report = run_harness(router)
    assert report.ok, report.to_dict()
    assert report.to_dict()["total"] >= 3


def test_benchmark_reports_latency():
    cfg = GatewayConfig(providers=[], timeout_seconds=10, max_retries=1)
    _reg, router = build_gateway(cfg)
    result = benchmark(router, iterations=3)
    assert result["iterations"] == 3
    assert result["errors"] == 0
    assert result["latency_ms_avg"] is not None
