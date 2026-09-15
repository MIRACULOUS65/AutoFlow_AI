"""Provider protocol and error types.

Every provider adapter (cloud API, OpenAI-compatible server, self-hosted, or the
local deterministic provider used in this slice) implements this contract. The
orchestration layer only ever talks to this interface, never a specific vendor.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas.models import ModelDefinition, ModelRequest, ModelResponse


class ProviderError(Exception):
    """A provider failed in a controlled way (safe to classify/fallback)."""


class ProviderTimeout(ProviderError):
    """A provider call exceeded its timeout budget."""


@runtime_checkable
class ModelProvider(Protocol):
    """Provider-neutral model interface.

    ``generate`` is synchronous in this slice for simplicity and testability;
    the contract can move to async without changing callers because the gateway
    mediates all access. ``prompt`` is the assembled, trust-separated prompt
    text (context assembly is a later phase); providers must treat it as data.
    """

    name: str

    def supports(self, model: ModelDefinition) -> bool:
        """Whether this provider can serve the given model definition."""
        ...

    def generate(
        self, model: ModelDefinition, request: ModelRequest, prompt: str
    ) -> ModelResponse:
        """Produce a normalized :class:`ModelResponse` for ``request``."""
        ...

    def health(self) -> bool:
        """Cheap liveness check."""
        ...
