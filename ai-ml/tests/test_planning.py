"""Phase 6 planning tests: typed graph, state machine, validator, planners."""

from __future__ import annotations

import pytest

from autoflow_ai.planning import (
    AgentType,
    NodeStatus,
    PlanNode,
    PlannerOutput,
    RuntimeGraph,
    is_valid_node_transition,
    validate_plan,
)
from autoflow_ai.planning.planner import DeterministicPlanner

pytestmark = pytest.mark.unit


def _node(task_id, deps=(), agent=AgentType.DOCUMENT, tools=(), caps=(), perms=()):
    return PlanNode(
        task_id=task_id,
        objective=f"do {task_id}",
        agent_type=agent,
        dependencies=deps,
        tool_requirements=tools,
        required_capabilities=caps,
        permission_requirements=perms,
    )


KNOWN_AGENTS = {a.value for a in AgentType}
TOOLS = {"document.inspect", "document.edit", "document.save", "document.verify"}
CAPS = {"document_editing", "verification", "research", "data_analysis"}
PERMS = {"files:read", "files:write"}


def _plan(nodes):
    return PlannerOutput(normalized_goal="g", nodes=nodes)


# -- node state machine ------------------------------------------------------


@pytest.mark.parametrize(
    "src,dst,ok",
    [
        (NodeStatus.PENDING, NodeStatus.READY, True),
        (NodeStatus.READY, NodeStatus.RUNNING, True),
        (NodeStatus.RUNNING, NodeStatus.SUCCEEDED, True),
        (NodeStatus.RUNNING, NodeStatus.FAILED, True),
        (NodeStatus.FAILED, NodeStatus.NEEDS_REPLAN, True),
        (NodeStatus.SUCCEEDED, NodeStatus.RUNNING, False),
        (NodeStatus.PENDING, NodeStatus.SUCCEEDED, False),
    ],
)
def test_node_transitions(src, dst, ok):
    assert is_valid_node_transition(src, dst) is ok


# -- validator ---------------------------------------------------------------


def test_valid_linear_plan():
    plan = _plan([
        _node("a", tools=("document.inspect",), caps=("document_editing",), perms=("files:read",)),
        _node("b", deps=("a",), tools=("document.edit",), caps=("document_editing",), perms=("files:write",)),
    ])
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS,
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert reasons == []


def test_reject_cycle():
    plan = _plan([_node("a", deps=("b",)), _node("b", deps=("a",))])
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS,
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert any("cycle" in r for r in reasons)


def test_reject_unknown_dependency():
    plan = _plan([_node("a", deps=("ghost",))])
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS,
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert any("unknown task" in r for r in reasons)


def test_reject_duplicate_ids():
    plan = _plan([_node("a"), _node("a")])
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS,
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert any("duplicate task ids" in r for r in reasons)


def test_reject_unregistered_tool():
    plan = _plan([_node("a", tools=("danger.shell",))])
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS,
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert any("unregistered tool" in r for r in reasons)


def test_reject_unavailable_capability():
    plan = _plan([_node("a", caps=("telepathy",))])
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS,
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert any("unavailable capability" in r for r in reasons)


def test_reject_ungranted_permission():
    plan = _plan([_node("a", perms=("prod:deploy",))])
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS,
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert any("ungranted permission" in r for r in reasons)


def test_reject_self_dependency():
    plan = _plan([_node("a", deps=("a",))])
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS,
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert any("self-dependency" in r for r in reasons)


# -- runtime graph -----------------------------------------------------------


def test_ready_nodes_respect_dependencies():
    g = RuntimeGraph(
        execution_id="exec_1", task_id="task_1", goal="g",
        nodes=[_node("a"), _node("b", deps=("a",))],
    )
    ready = [n.task_id for n in g.ready_nodes()]
    assert ready == ["a"]  # b blocked until a succeeds
    g.node("a").status = NodeStatus.SUCCEEDED
    ready = [n.task_id for n in g.ready_nodes()]
    assert "b" in ready


def test_graph_completion_and_failure():
    g = RuntimeGraph(execution_id="e", task_id="t", goal="g", nodes=[_node("a")])
    assert not g.is_complete()
    g.node("a").status = NodeStatus.FAILED
    assert g.is_complete()
    assert g.has_failure()


# -- deterministic planner ---------------------------------------------------


def test_deterministic_document_plan():
    plan = DeterministicPlanner().plan("edit this word file and save it", target_path="/x/a.docx")
    ids = [n.task_id for n in plan.nodes]
    assert ids == ["t_inspect", "t_edit", "t_save", "t_verify"]
    assert plan.nodes[-1].agent_type == AgentType.QA


def test_deterministic_research_plan_is_parallel():
    plan = DeterministicPlanner().plan("research the top competitors and summarize")
    # two independent research nodes fan into synthesis
    research = [n for n in plan.nodes if n.agent_type == AgentType.RESEARCH]
    assert len(research) >= 2
    synth = [n for n in plan.nodes if not n.dependencies and n.agent_type == AgentType.RESEARCH]
    assert synth  # research nodes have no dependencies -> parallelizable


def test_deterministic_plan_always_valid():
    plan = DeterministicPlanner().plan("do something vague")
    reasons = validate_plan(plan, known_agents=KNOWN_AGENTS, registered_tools=TOOLS | {"document.verify"},
                            available_capabilities=CAPS, granted_permissions=PERMS)
    assert reasons == []
