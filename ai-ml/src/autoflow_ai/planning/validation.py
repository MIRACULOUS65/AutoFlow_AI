"""Deterministic plan validation. A plan is executable only after this passes."""

from __future__ import annotations

from .errors import PlanValidationError
from .models import AgentType, PlannerOutput


def validate_plan(
    plan: PlannerOutput,
    *,
    known_agents: set[str],
    registered_tools: set[str],
    available_capabilities: set[str],
    granted_permissions: set[str],
) -> list[str]:
    """Return a list of validation errors (empty => valid). Callers raise
    :class:`PlanValidationError` to fail closed."""

    reasons: list[str] = []
    ids = [n.task_id for n in plan.nodes]
    id_set = set(ids)

    # duplicate task ids
    if len(ids) != len(id_set):
        dupes = sorted({x for x in ids if ids.count(x) > 1})
        reasons.append(f"duplicate task ids: {dupes}")

    # dependency references + self-deps
    for n in plan.nodes:
        for dep in n.dependencies:
            if dep == n.task_id:
                reasons.append(f"self-dependency: {n.task_id}")
            elif dep not in id_set:
                reasons.append(f"task {n.task_id!r} depends on unknown task {dep!r}")

    # unknown agents
    for n in plan.nodes:
        if str(n.agent_type) not in known_agents:
            reasons.append(f"task {n.task_id!r} assigns unknown agent {n.agent_type}")

    # unknown/unregistered tools
    for n in plan.nodes:
        for tool in n.tool_requirements:
            if tool not in registered_tools:
                reasons.append(f"task {n.task_id!r} requires unregistered tool {tool!r}")

    # unavailable capabilities
    for n in plan.nodes:
        for cap in n.required_capabilities:
            if cap not in available_capabilities:
                reasons.append(f"task {n.task_id!r} requires unavailable capability {cap!r}")

    # unauthorized permissions
    for n in plan.nodes:
        for perm in n.permission_requirements:
            if perm not in granted_permissions:
                reasons.append(f"task {n.task_id!r} requires ungranted permission {perm!r}")

    # cycle detection (Kahn)
    indegree = {i: 0 for i in id_set}
    adjacency: dict[str, list[str]] = {i: [] for i in id_set}
    for n in plan.nodes:
        for dep in n.dependencies:
            if dep in id_set:
                adjacency[dep].append(n.task_id)
                indegree[n.task_id] += 1
    queue = [i for i, d in indegree.items() if d == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in adjacency[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited != len(id_set):
        reasons.append("plan contains a dependency cycle")

    # high-risk nodes must require approval + verification
    from ..schemas.enums import RiskClass

    for n in plan.nodes:
        if n.risk_level in (RiskClass.HIGH, RiskClass.CRITICAL):
            if not n.approval_required:
                reasons.append(f"high-risk task {n.task_id!r} must require approval")
            if not n.verification_requirements:
                reasons.append(f"high-risk task {n.task_id!r} must define verification")

    return reasons
