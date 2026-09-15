"""Retry, fallback and health policies for the model gateway.

These bound how hard the gateway tries a single provider (RetryPolicy) and
whether it may move to the next eligible model (FallbackPolicy). ProviderHealth
tracks recent success/failure so a flapping provider can be de-prioritized.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .provider import ProviderError, ProviderTimeout


@dataclass
class RetryPolicy:
    """Bounded retry for a single provider on transient failure."""

    max_attempts: int = 2          # total attempts per provider (>=1)
    base_delay_seconds: float = 0.0  # 0 keeps tests fast; real use > 0
    backoff_factor: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

    def delay_for(self, attempt: int) -> float:
        if self.base_delay_seconds <= 0:
            return 0.0
        return self.base_delay_seconds * (self.backoff_factor ** (attempt - 1))

    @staticmethod
    def is_retryable(exc: Exception) -> bool:
        # Timeouts and generic provider errors are retryable; auth errors are
        # not (handled by the caller which raises a non-retryable subtype).
        if isinstance(exc, ProviderTimeout):
            return True
        if isinstance(exc, ProviderError):
            return not getattr(exc, "non_retryable", False)
        return False


@dataclass
class FallbackPolicy:
    """Whether the router may fall back to the next eligible model."""

    enabled: bool = True
    max_models: int = 3  # cap how many models to try in one request


@dataclass
class ProviderHealth:
    """Rolling health for a provider (used to de-prioritize flappers)."""

    consecutive_failures: int = 0
    total_calls: int = 0
    total_failures: int = 0
    last_error: str | None = None
    _healthy: bool = field(default=True)

    def record_success(self) -> None:
        self.total_calls += 1
        self.consecutive_failures = 0
        self._healthy = True

    def record_failure(self, error: str) -> None:
        self.total_calls += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.last_error = error
        if self.consecutive_failures >= 3:
            self._healthy = False

    @property
    def healthy(self) -> bool:
        return self._healthy

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_failures / self.total_calls


def sleep(seconds: float) -> None:
    """Indirection so tests can monkeypatch sleeping to a no-op."""

    if seconds > 0:
        time.sleep(seconds)
