"""Planning error types."""

from __future__ import annotations


class PlanningError(Exception):
    """Base class for planning errors."""


class PlanValidationError(PlanningError):
    """A generated plan failed deterministic validation (fail closed)."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))
