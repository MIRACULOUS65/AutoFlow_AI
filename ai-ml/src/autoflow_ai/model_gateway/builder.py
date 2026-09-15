"""Build a ModelRegistry + ModelRouter from configuration.

If a real provider is configured via environment variables, it is registered
alongside the deterministic local provider (which stays available for tests and
offline runs). With no real provider configured, the gateway is local-only, so
the whole system still runs headlessly without network or API keys.
"""

from __future__ import annotations

from ..schemas.enums import DeploymentType, ModelRole
from ..schemas.models import ModelCapability, ModelDefinition
from .config import GatewayConfig, ProviderConfig, load_gateway_config
from .http_provider import OpenAICompatibleProvider
from .local_provider import LocalRuleProvider, default_local_model
from .policies import RetryPolicy
from .registry import ModelRegistry
from .router import ModelRouter

# Provider adapter factories keyed by config ``provider`` string.
_PROVIDER_KINDS = {"openai_compatible", "openai", "vllm", "self_hosted"}


def _model_id_for(cfg: ProviderConfig) -> str:
    # deterministic, prefix-valid id derived from the role prefix
    return f"model_{cfg.role_prefix.lower()}01"


def _definition_for(cfg: ProviderConfig, priority: int) -> ModelDefinition:
    return ModelDefinition(
        model_id=_model_id_for(cfg),
        provider="openai_compatible",
        provider_model_name=cfg.model_id,
        display_name=f"{cfg.role_prefix.title()} ({cfg.model_id})",
        roles=(ModelRole.PLANNER, ModelRole.EXECUTOR, ModelRole.TOOL_CALLER),
        capabilities=ModelCapability(
            text=True,
            tool_calling=True,
            structured_output=True,
            reasoning=True,
            streaming=cfg.requires_streaming,
        ),
        context_window=cfg.context_window,
        max_output_tokens=min(4096, cfg.context_window),
        deployment=DeploymentType.OPENAI_COMPATIBLE,
        routing_priority=priority,
        requires_streaming=cfg.requires_streaming,
    )


def build_gateway(
    config: GatewayConfig | None = None,
    *,
    transport=None,
    stream_transport=None,
) -> tuple[ModelRegistry, ModelRouter]:
    """Return (registry, router) assembled from config.

    ``transport`` is an optional injection point for the HTTP provider (used by
    tests to avoid real network calls).
    """

    cfg = config or load_gateway_config()
    registry = ModelRegistry()

    # Real providers get higher priority than the local fallback.
    priority = 200
    for pc in cfg.providers:
        if pc.provider not in _PROVIDER_KINDS:
            # Unknown provider kind (e.g. local-rule via env) — skip; local is
            # always added below.
            continue
        if not pc.base_url:
            # Cannot talk to an HTTP provider without a base URL; skip safely.
            continue
        provider = OpenAICompatibleProvider(
            base_url=pc.base_url,
            api_key=pc.api_key,
            timeout_seconds=cfg.timeout_seconds,
            transport=transport,
            stream_transport=stream_transport,
        )
        registry.register(_definition_for(pc, priority), provider)
        priority -= 10

    if cfg.include_local or len(registry) == 0:
        # Local provider always available as a low-priority deterministic path.
        local_def = default_local_model().model_copy(update={"routing_priority": 50})
        registry.register(local_def, LocalRuleProvider())

    router = ModelRouter(
        registry,
        retry_policy=RetryPolicy(max_attempts=cfg.max_retries + 1),
    )
    return registry, router
