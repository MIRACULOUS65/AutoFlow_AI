"""Context budget and allocation policy.

Reserves output tokens FIRST, then allocates the remaining input budget across
sections. Numbers are configurable and derived from the model's context window,
so no single window size is hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .items import ContextSection


@dataclass
class ContextBudget:
    """Resolved token budget for one model request."""

    context_window: int
    reserved_output_tokens: int
    input_budget: int
    section_budgets: dict[ContextSection, int] = field(default_factory=dict)

    def budget_for(self, section: ContextSection) -> int:
        return self.section_budgets.get(section, 0)


# Default relative weights for splitting the input budget across sections.
# High-authority/always-needed sections get guaranteed shares; knowledge/memory
# get the bulk of the flexible remainder.
_DEFAULT_WEIGHTS: dict[ContextSection, float] = {
    ContextSection.SYSTEM_POLICY: 0.06,
    ContextSection.TASK_INSTRUCTION: 0.10,
    ContextSection.IDENTITY: 0.02,
    ContextSection.WORKSPACE: 0.02,
    ContextSection.PERMISSIONS: 0.04,
    ContextSection.CURRENT_WORKFLOW: 0.06,
    ContextSection.CURRENT_STEP: 0.08,
    ContextSection.AUTHORIZED_KNOWLEDGE: 0.28,
    ContextSection.WORKFLOW_MEMORY: 0.10,
    ContextSection.CURRENT_OBSERVATION: 0.08,
    ContextSection.TOOL_RESULTS: 0.06,
    ContextSection.RECOVERY_HISTORY: 0.04,
    ContextSection.APPROVAL_STATE: 0.02,
    ContextSection.OUTPUT_CONTRACT: 0.04,
}


class ContextBudgetPolicy:
    """Allocates a model's context window across sections, output reserved."""

    def __init__(
        self,
        *,
        output_reserve_ratio: float = 0.25,
        min_output_tokens: int = 256,
        weights: dict[ContextSection, float] | None = None,
    ) -> None:
        if not 0 < output_reserve_ratio < 1:
            raise ValueError("output_reserve_ratio must be between 0 and 1")
        self._reserve_ratio = output_reserve_ratio
        self._min_output = min_output_tokens
        self._weights = weights or dict(_DEFAULT_WEIGHTS)

    def allocate(self, context_window: int) -> ContextBudget:
        if context_window <= 0:
            raise ValueError("context_window must be > 0")

        reserved = max(self._min_output, int(context_window * self._reserve_ratio))
        reserved = min(reserved, context_window - 1)
        input_budget = context_window - reserved

        total_weight = sum(self._weights.values()) or 1.0
        section_budgets: dict[ContextSection, int] = {}
        for section, weight in self._weights.items():
            section_budgets[section] = int(input_budget * (weight / total_weight))

        return ContextBudget(
            context_window=context_window,
            reserved_output_tokens=reserved,
            input_budget=input_budget,
            section_budgets=section_budgets,
        )
