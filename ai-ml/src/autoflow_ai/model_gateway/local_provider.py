"""Deterministic local provider (no network, no API keys).

This is NOT a fake LLM. It is an honest, rule-based provider that implements the
same :class:`ModelProvider` contract as any cloud model. It lets the entire
orchestration pipeline run offline and deterministically for the first vertical
slice. The intelligence it provides is intentionally simple (keyword/rule based)
and is clearly labelled as such in its output (``provider="local-rule"``).

When a real cloud/self-hosted provider is added later, the orchestration code
does not change: it still requests capabilities and receives a ModelResponse.
"""

from __future__ import annotations

import time

from ..schemas.models import ModelDefinition, ModelRequest, ModelResponse, ModelUsage


class LocalRuleProvider:
    """A deterministic, offline provider used for the headless slice."""

    name = "local-rule"

    def __init__(self, *, latency_ms: int = 0) -> None:
        self._latency_ms = latency_ms
        self._healthy = True

    def supports(self, model: ModelDefinition) -> bool:
        return model.provider == self.name

    def health(self) -> bool:
        return self._healthy

    def generate(
        self, model: ModelDefinition, request: ModelRequest, prompt: str
    ) -> ModelResponse:
        if self._latency_ms:
            time.sleep(self._latency_ms / 1000.0)

        # The local provider echoes a structured acknowledgement. The actual
        # decision logic (intent detection, edit-op selection) lives in the
        # deterministic normalizer/planner/agent components, which is the honest
        # place for rule-based reasoning. The provider's job is only to satisfy
        # the model contract so the pipeline exercises the real seam.
        structured = {
            "provider": self.name,
            "role": str(request.required_role),
            "prompt_chars": len(prompt),
            "acknowledged": True,
        }
        usage = ModelUsage(
            input_tokens=max(1, len(prompt) // 4),
            output_tokens=8,
            latency_ms=self._latency_ms,
        )
        return ModelResponse(
            request_id=request.request_id,
            model_id=model.model_id,
            provider=self.name,
            finish_reason="stop",
            structured_output=structured,
            usage=usage,
        )


def default_local_model() -> ModelDefinition:
    """A ModelDefinition wired to the local rule provider."""

    from ..schemas.enums import DeploymentType, ModelRole
    from ..schemas.models import ModelCapability

    return ModelDefinition(
        model_id="model_local01",
        provider="local-rule",
        provider_model_name="rule-engine-v1",
        display_name="Local Rule Engine",
        roles=(
            ModelRole.PLANNER,
            ModelRole.EXECUTOR,
            ModelRole.TOOL_CALLER,
        ),
        capabilities=ModelCapability(
            text=True,
            tool_calling=True,
            structured_output=True,
            reasoning=True,
        ),
        context_window=32_000,
        max_output_tokens=4_096,
        deployment=DeploymentType.LOCAL,
        expected_latency_ms=0,
    )
