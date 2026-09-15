"""Dynamic planning (Phase 6).

Typed planner output, a runtime task-graph with an explicit state machine, and a
deterministic validator. The planner PROPOSES a graph; the runtime decides what
is executable. This composes on the Phase 1 ``schemas.tasks`` DAG concepts but
adds mutable per-execution runtime state (node status), which the immutable
schema graph intentionally does not carry.
"""

from __future__ import annotations

from .errors import PlanningError, PlanValidationError
from .models import (
    AgentType,
    NodeStatus,
    PlannerOutput,
    PlanNode,
    ReuseMode,
    RuntimeGraph,
    is_valid_node_transition,
)
from .validation import validate_plan

__all__ = [
    "PlanningError",
    "PlanValidationError",
    "AgentType",
    "NodeStatus",
    "ReuseMode",
    "PlanNode",
    "RuntimeGraph",
    "PlannerOutput",
    "is_valid_node_transition",
    "validate_plan",
]
