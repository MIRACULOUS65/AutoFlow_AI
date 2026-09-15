"""Computer-use error types (all fail closed)."""

from __future__ import annotations


class ComputerUseError(Exception):
    """Base class for computer-use errors."""


class AdapterUnavailable(ComputerUseError):
    """No interactive desktop / UI Automation backend is available."""


class ElementNotFound(ComputerUseError):
    """A requested UI element could not be resolved."""


class AmbiguousTarget(ComputerUseError):
    """Multiple UI elements matched — the runtime must refine, never guess."""

    def __init__(self, count: int, query: str) -> None:
        self.count = count
        self.query = query
        super().__init__(f"ambiguous target ({count} matches) for {query}")


class UnsafeOperation(ComputerUseError):
    """A requested operation is destructive/unauthorized and is refused."""
