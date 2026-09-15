"""Model router: capability-based selection with retry + bounded fallback.

Selection considers capability match (via ModelDefinition.satisfies), provider
health (static definition health + dynamic ProviderHealth), and routing
priority. For each eligible model the router applies a RetryPolicy (retry the
same provider on transient failure); if the model is exhausted it falls back to
the next eligible model per the FallbackPolicy. The model actually used and
whether it was a fallback are recorded on the response.

Backward compatible: ``ModelRouter(registry)`` still works with defaults.
"""

from __future__ import annotations

from ..schemas.models import ModelRequest, ModelResponse
from .policies import FallbackPolicy, ProviderHealth, RetryPolicy, sleep
from .provider import ProviderError
from .registry import ModelRegistry


class NoEligibleModel(Exception):
    """No registered model satisfies the request."""


class ModelRouter:
    def __init__(
        self,
        registry: ModelRegistry,
        *,
        retry_policy: RetryPolicy | None = None,
        fallback_policy: FallbackPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._retry = retry_policy or RetryPolicy()
        self._fallback = fallback_policy or FallbackPolicy()
        self._health: dict[str, ProviderHealth] = {}

    # -- introspection -------------------------------------------------------

    def health_for(self, provider_name: str) -> ProviderHealth:
        return self._health.setdefault(provider_name, ProviderHealth())

    def eligible(self, request: ModelRequest):
        """Return eligible (model, provider) pairs, best-first."""

        pairs = []
        for model in self._registry.models():
            if not model.satisfies(request):
                continue
            provider = self._registry.provider_for(model.model_id)
            pairs.append((model, provider))

        def sort_key(mp):
            model, provider = mp
            health = self.health_for(provider.name)
            # unhealthy providers sink to the bottom; then priority; then id.
            return (0 if health.healthy else 1, -model.routing_priority, model.model_id)

        pairs.sort(key=sort_key)
        return pairs

    # -- generation ----------------------------------------------------------

    def generate(self, request: ModelRequest, prompt: str) -> ModelResponse:
        """Route with per-provider retry and bounded cross-model fallback."""

        candidates = self.eligible(request)
        if not candidates:
            raise NoEligibleModel(
                f"no model satisfies role={request.required_role} "
                f"caps={request.required_capabilities}"
            )

        max_models = self._fallback.max_models if self._fallback.enabled else 1
        candidates = candidates[:max_models] if max_models else candidates

        last_error: Exception | None = None
        for index, (model, provider) in enumerate(candidates):
            health = self.health_for(provider.name)

            if not provider.health():
                last_error = ProviderError(f"provider {provider.name!r} unhealthy")
                health.record_failure("provider reported unhealthy")
                continue

            response = self._attempt_with_retry(model, provider, request, prompt)
            if response is not None:
                health.record_success()
                if index > 0:
                    response = response.model_copy(update={"is_fallback": True})
                return response
            last_error = self._last_attempt_error

            if not self._fallback.enabled:
                break

        raise NoEligibleModel(
            f"all {len(candidates)} eligible model(s) failed; last error: {last_error!r}"
        )

    def _attempt_with_retry(self, model, provider, request, prompt):
        """Try a single provider up to RetryPolicy.max_attempts. Returns the
        response or None (setting self._last_attempt_error)."""

        self._last_attempt_error = None
        health = self.health_for(provider.name)
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                return provider.generate(model, request, prompt)
            except ProviderError as exc:
                self._last_attempt_error = exc
                health.record_failure(repr(exc))
                if not RetryPolicy.is_retryable(exc):
                    return None
                if attempt < self._retry.max_attempts:
                    sleep(self._retry.delay_for(attempt))
        return None
