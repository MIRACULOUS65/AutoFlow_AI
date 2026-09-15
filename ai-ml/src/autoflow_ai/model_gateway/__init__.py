"""Model gateway: provider-neutral model access.

The application asks for capabilities; the gateway picks an eligible model and
calls a provider adapter. A deterministic local provider (no network, no API
keys) is always available so the pipeline runs offline; real cloud/self-hosted
providers (OpenAI-compatible endpoints) are added via environment config and
implement the same :class:`ModelProvider` protocol.
"""

from __future__ import annotations

from .builder import build_gateway
from .config import GatewayConfig, ProviderConfig, load_gateway_config
from .harness import HarnessReport, benchmark, run_harness
from .http_provider import AuthenticationError, OpenAICompatibleProvider
from .local_provider import LocalRuleProvider, default_local_model
from .policies import FallbackPolicy, ProviderHealth, RetryPolicy
from .provider import ModelProvider, ProviderError, ProviderTimeout
from .registry import ModelRegistry
from .router import ModelRouter, NoEligibleModel
from .structured import StructuredOutputError, StructuredOutputParser, extract_json, parse_into

__all__ = [
    # protocol / errors
    "ModelProvider",
    "ProviderError",
    "ProviderTimeout",
    "AuthenticationError",
    # providers
    "LocalRuleProvider",
    "default_local_model",
    "OpenAICompatibleProvider",
    # registry / router
    "ModelRegistry",
    "ModelRouter",
    "NoEligibleModel",
    # policies
    "RetryPolicy",
    "FallbackPolicy",
    "ProviderHealth",
    # config
    "GatewayConfig",
    "ProviderConfig",
    "load_gateway_config",
    # builder
    "build_gateway",
    # structured output
    "StructuredOutputParser",
    "StructuredOutputError",
    "extract_json",
    "parse_into",
    # harness
    "run_harness",
    "benchmark",
    "HarnessReport",
]
