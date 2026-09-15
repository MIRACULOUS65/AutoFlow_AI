"""Agent brain: intent normalization, planning and agent assignment.

For the vertical slice the reasoning is deterministic/rule-based, but it uses
the real contracts (NormalizedTask, TaskGraph) and the real model gateway seam
so cloud models can later replace the rule logic without changing callers.
"""

from __future__ import annotations

from .normalizer import IntentNormalizer, NormalizeError
from .planner import Planner, PlanError

__all__ = ["IntentNormalizer", "NormalizeError", "Planner", "PlanError"]
