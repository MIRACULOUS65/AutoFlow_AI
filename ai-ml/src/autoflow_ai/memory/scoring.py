"""Deterministic workflow scoring and compatibility."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from .config import MemoryConfig
from .models import CompatibilityLevel, WorkflowMemory, WorkflowScore


class WorkflowScorer:
    """Combines semantic similarity, compatibility, verified success, recency.

    Not probabilistic confidence — explainable weighted components. Usage count
    alone never dominates; a high-usage-but-failing workflow scores below a
    low-usage perfectly-verified one via the success component + failure decay.
    """

    def __init__(self, config: MemoryConfig) -> None:
        self._c = config

    def score(
        self,
        wf: WorkflowMemory,
        *,
        semantic: float,
        compatibility: float,
        now: datetime | None = None,
    ) -> WorkflowScore:
        now = now or datetime.now(timezone.utc)
        success = wf.verified_success_rate
        if self._c.failure_decay and wf.failure_count:
            # decay success signal by failure ratio
            success *= 1.0 / (1.0 + wf.failure_count)
        recency = self._recency(wf, now)

        total = (
            self._c.semantic_weight * semantic
            + self._c.compatibility_weight * compatibility
            + self._c.success_weight * success
            + self._c.recency_weight * recency
        )
        total = max(0.0, min(1.0, total))
        return WorkflowScore(
            semantic=round(semantic, 4),
            compatibility=round(compatibility, 4),
            success=round(success, 4),
            recency=round(recency, 4),
            total=round(total, 4),
        )

    @staticmethod
    def _recency(wf: WorkflowMemory, now: datetime) -> float:
        ref = wf.updated_at or wf.created_at
        age_days = max(0.0, (now - ref).total_seconds() / 86400.0)
        # exponential decay with ~30-day half-life
        return math.exp(-age_days / 43.0)


class CompatibilityChecker:
    """Evaluate whether a stored workflow can run in the current context."""

    def check(
        self,
        wf: WorkflowMemory,
        *,
        available_tools: set[str],
        available_capabilities: set[str],
        provided_parameters: dict | None = None,
    ) -> tuple[CompatibilityLevel, list[str]]:
        reasons: list[str] = []
        provided = provided_parameters or {}

        required_tools = set(wf.workflow.tools)
        missing_tools = required_tools - available_tools
        if missing_tools:
            reasons.append(f"missing tools: {sorted(missing_tools)}")

        required_caps = set(wf.workflow.capabilities)
        missing_caps = required_caps - available_capabilities
        if missing_caps:
            reasons.append(f"missing capabilities: {sorted(missing_caps)}")

        missing_params = [
            p.name for p in wf.workflow.parameters if p.required and p.name not in provided and p.default is None
        ]
        if missing_params:
            reasons.append(f"missing required parameters: {missing_params}")

        if missing_tools or missing_caps:
            return CompatibilityLevel.INCOMPATIBLE, reasons
        if missing_params:
            return CompatibilityLevel.PARTIALLY_COMPATIBLE, reasons
        return CompatibilityLevel.COMPATIBLE, reasons
