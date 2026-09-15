"""Memory error types."""

from __future__ import annotations


class MemoryError(Exception):
    """Base class for memory errors."""


class PromotionRejected(MemoryError):
    """A workflow candidate did not satisfy the promotion policy."""


class CompatibilityError(MemoryError):
    """A workflow is not compatible with the current context."""
