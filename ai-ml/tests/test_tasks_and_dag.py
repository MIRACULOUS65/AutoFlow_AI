"""Tests for task/planning contracts and DAG validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autoflow_ai.schemas import (
    AgentKind,
    RiskClass,
    TaskEdge,
    TaskGraph,
    TaskNode,
    VerificationRequirement,
)

pytestmark = pytest.mark.contract


def _node(step_id: str, *, risk=RiskClass.LOW, verify=(), approval=False) -> TaskNode:
    return TaskNode(
        step_id=step_id,
        objective=f"do {step_id}",
        assigned_agent=AgentKind.DOCUMENT,
        risk=risk,
        verification=verify,
        requires_approval=approval,
    )


def test_valid_linear_graph_topo_order():
    g = TaskGraph(
        task_id="task_1",
        goal="g",
        nodes=(_node("step_a"), _node("step_b"), _node("step_c")),
        edges=(
            TaskEdge(from_step="step_a", to_step="step_b"),
            TaskEdge(from_step="step_b", to_step="step_c"),
        ),
    )
    assert g.topological_order() == ("step_a", "step_b", "step_c")
    assert g.roots() == ("step_a",)
    assert g.dependencies_of("step_b") == ("step_a",)


def test_graph_rejects_cycle():
    with pytest.raises(ValidationError, match="cycle"):
        TaskGraph(
            task_id="task_1",
            goal="g",
            nodes=(_node("step_a"), _node("step_b")),
            edges=(
                TaskEdge(from_step="step_a", to_step="step_b"),
                TaskEdge(from_step="step_b", to_step="step_a"),
            ),
        )


def test_graph_rejects_edge_to_unknown_step():
    with pytest.raises(ValidationError, match="unknown step"):
        TaskGraph(
            task_id="task_1",
            goal="g",
            nodes=(_node("step_a"),),
            edges=(TaskEdge(from_step="step_a", to_step="step_ghost"),),
        )


def test_graph_rejects_duplicate_step_ids():
    with pytest.raises(ValidationError, match="duplicate step ids"):
        TaskGraph(
            task_id="task_1",
            goal="g",
            nodes=(_node("step_a"), _node("step_a")),
        )


def test_graph_rejects_duplicate_edges():
    with pytest.raises(ValidationError, match="duplicate dependency"):
        TaskGraph(
            task_id="task_1",
            goal="g",
            nodes=(_node("step_a"), _node("step_b")),
            edges=(
                TaskEdge(from_step="step_a", to_step="step_b"),
                TaskEdge(from_step="step_a", to_step="step_b"),
            ),
        )


def test_graph_requires_at_least_one_node():
    with pytest.raises(ValidationError, match="at least one node"):
        TaskGraph(task_id="task_1", goal="g", nodes=())


def test_edge_rejects_self_loop():
    with pytest.raises(ValidationError, match="self-dependency"):
        TaskEdge(from_step="step_a", to_step="step_a")


def test_high_risk_node_requires_verification_and_approval():
    # missing verification
    with pytest.raises(ValidationError, match="must define"):
        _node("step_x", risk=RiskClass.HIGH, approval=True)
    # missing approval
    with pytest.raises(ValidationError, match="requires_approval"):
        _node(
            "step_x",
            risk=RiskClass.HIGH,
            verify=(VerificationRequirement(check_id="c", description="d"),),
            approval=False,
        )
    # valid high-risk node
    ok = _node(
        "step_x",
        risk=RiskClass.HIGH,
        verify=(VerificationRequirement(check_id="c", description="d"),),
        approval=True,
    )
    assert ok.requires_approval


def test_parallel_graph_topo_order_is_valid():
    g = TaskGraph(
        task_id="task_1",
        goal="g",
        nodes=(_node("step_a"), _node("step_b"), _node("step_c"), _node("step_d")),
        edges=(
            TaskEdge(from_step="step_a", to_step="step_d"),
            TaskEdge(from_step="step_b", to_step="step_d"),
            TaskEdge(from_step="step_c", to_step="step_d"),
        ),
    )
    order = g.topological_order()
    # d must come after a, b, c
    assert order.index("step_d") == 3
    assert set(order) == {"step_a", "step_b", "step_c", "step_d"}
