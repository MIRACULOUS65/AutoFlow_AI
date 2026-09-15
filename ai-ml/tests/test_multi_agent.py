"""Phase 6 multi-agent runtime tests: MA golden tasks, adversarial, concurrency."""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import docx
import pytest

from autoflow_ai.agents.models import AgentContext, AgentResult, AgentStatus, AgentActionProposal
from autoflow_ai.agents.registry import AgentRegistry, build_default_registry
from autoflow_ai.agents.base import SpecialistAgent
from autoflow_ai.planning.models import AgentType, NodeStatus, PlanNode, RuntimeGraph
from autoflow_ai.runtime import DocumentSession, ToolRegistry
from autoflow_ai.runtime.document_tools import register_document_tools
from autoflow_ai.runtime.multi_agent import MultiAgentRuntime
from autoflow_ai.orchestrator import AutoFlow

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent / "fixtures" / "sample.docx"
PERMS = frozenset({"files:read", "files:write"})
DOC_PROMPT = 'Edit this Word file, fix wording, normalize em-dashes, remove double spaces, and save. Replace "teh" with "the".'


def _doc_tools():
    reg = ToolRegistry()
    register_document_tools(reg, DocumentSession())
    return reg


def _runtime(tools=None, agents=None, **kw):
    return MultiAgentRuntime(
        agents=agents or build_default_registry(),
        tools=tools or _doc_tools(),
        permissions=PERMS,
        max_concurrency=kw.pop("max_concurrency", 4),
        max_replans=kw.pop("max_replans", 2),
        **kw,
    )


def _graph(nodes, execution_id="exec_t"):
    return RuntimeGraph(execution_id=execution_id, task_id="task_t", goal="g", nodes=nodes)


# ============================ MA golden tasks ==============================


# MA01 / MA24: full document workflow through the runtime
def test_ma01_document_workflow(tmp_path):
    dest = tmp_path / "a.docx"
    shutil.copy(FIXTURE, dest)
    app = AutoFlow.build()
    report = app.run_multi_agent(DOC_PROMPT, target_path=str(dest))
    assert report.ok, report.error
    text = "\n".join(p.text for p in docx.Document(str(dest)).paragraphs)
    assert "teh" not in text and "This document has" in text


# MA02: inspect only
def test_ma02_inspect_only(tmp_path):
    dest = tmp_path / "a.docx"
    shutil.copy(FIXTURE, dest)
    tools = _doc_tools()
    node = PlanNode(
        task_id="t_inspect", objective="inspect", agent_type=AgentType.DOCUMENT,
        tool_requirements=("document.inspect",),
        parameters={"tool": "document.inspect", "path": str(dest)},
    )
    report = _runtime(tools=tools).run(_graph([node]))
    assert report.ok


# MA06: research produces structured findings (no side effect)
def test_ma06_research_finding():
    node = PlanNode(
        task_id="t_res", objective="research topic", agent_type=AgentType.RESEARCH,
        parameters={"context_summary": "the approved weekly process runs Monday"},
    )
    report = _runtime().run(_graph([node]))
    assert report.ok
    assert report.graph.node("t_res").output["finding"]


# MA07 / MA20: independent research runs concurrently, fans into synthesis
def test_ma07_ma20_parallel_research_fanin():
    nodes = [
        PlanNode(task_id="t_a", objective="A", agent_type=AgentType.RESEARCH),
        PlanNode(task_id="t_b", objective="B", agent_type=AgentType.RESEARCH),
        PlanNode(task_id="t_c", objective="C", agent_type=AgentType.RESEARCH),
        PlanNode(task_id="t_synth", objective="combine", agent_type=AgentType.SPREADSHEET,
                 dependencies=("t_a", "t_b", "t_c")),
    ]
    report = _runtime().run(_graph(nodes))
    assert report.ok
    assert report.graph.node("t_synth").status == NodeStatus.SUCCEEDED


# MA14: bounded replan recovers a failed node
def test_ma14_bounded_replan():
    # node fails first, replanner swaps its agent to a working research node
    # BrowserAgent is real now; force a genuine UNSUPPORTED failure by giving it
    # a tool outside its capability, then replan it to a working research node.
    nodes = [
        PlanNode(task_id="t_x", objective="unsupported", agent_type=AgentType.BROWSER,
                 parameters={"tool": "document.edit"}),
    ]

    def replanner(graph, failed):
        for n in failed:
            n.agent_type = AgentType.RESEARCH
            n.status = NodeStatus.NEEDS_REPLAN
            n.status = NodeStatus.READY
        return True

    report = _runtime(replanner=replanner, max_replans=2).run(_graph(nodes))
    assert report.ok
    assert report.replans == 1


# MA15: unavailable tool -> fail closed
def test_ma15_unavailable_tool():
    node = PlanNode(
        task_id="t_x", objective="use missing tool", agent_type=AgentType.DOCUMENT,
        parameters={"tool": "document.nonexistent"},
    )
    report = _runtime().run(_graph([node]))
    assert not report.ok
    assert report.graph.node("t_x").status == NodeStatus.FAILED


# MA16: malformed agent output (agent raises) -> fail closed
def test_ma16_malformed_agent_output():
    class BrokenAgent(SpecialistAgent):
        agent_type = AgentType.DOCUMENT
        capabilities = ("document_editing",)

        def propose(self, context):
            raise RuntimeError("boom")

    reg = AgentRegistry()
    reg.register(BrokenAgent())
    node = PlanNode(task_id="t_x", objective="x", agent_type=AgentType.DOCUMENT)
    report = _runtime(agents=reg).run(_graph([node]))
    assert not report.ok


# MA17: unregistered tool proposal rejected
def test_ma17_unregistered_tool_rejected():
    class RogueAgent(SpecialistAgent):
        agent_type = AgentType.DOCUMENT
        capabilities = ("document_editing",)

        def propose(self, context):
            return AgentResult(status=AgentStatus.OK, proposed_action=AgentActionProposal(tool_name="rogue.tool"))

    reg = AgentRegistry()
    reg.register(RogueAgent())
    node = PlanNode(task_id="t_x", objective="x", agent_type=AgentType.DOCUMENT)
    report = _runtime(agents=reg).run(_graph([node]))
    assert not report.ok
    assert any(e.type == "ACTION_REJECTED" for e in report.events)


# MA18: unauthorized operation blocked (permission)
def test_ma18_unauthorized_blocked(tmp_path):
    dest = tmp_path / "a.docx"
    shutil.copy(FIXTURE, dest)
    tools = _doc_tools()
    runtime = MultiAgentRuntime(
        agents=build_default_registry(), tools=tools,
        permissions=frozenset(),  # no files:read/write
    )
    node = PlanNode(
        task_id="t_inspect", objective="inspect", agent_type=AgentType.DOCUMENT,
        parameters={"tool": "document.inspect", "path": str(dest)},
    )
    report = runtime.run(_graph([node]))
    assert not report.ok
    assert any(e.type == "ACTION_REJECTED" and "permission" in e.detail for e in report.events)


# MA19: approval-required tool waits/blocks (email.send is high-risk)
def test_ma19_approval_required_blocks():
    from autoflow_ai.schemas.tools import ToolDefinition
    from autoflow_ai.schemas.enums import RiskClass

    tools = _doc_tools()
    tools.register(
        ToolDefinition(
            name="email.send", description="send", risk_class=RiskClass.HIGH,
            permission_scope="files:write", requires_approval=True,
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        lambda args: {"sent": True},
    )

    class CommAgent(SpecialistAgent):
        agent_type = AgentType.COMMUNICATION
        capabilities = ("communication",)

        def propose(self, context):
            return AgentResult(status=AgentStatus.OK, proposed_action=AgentActionProposal(tool_name="email.send"))

    reg = build_default_registry()
    reg.register(CommAgent())
    node = PlanNode(task_id="t_send", objective="send", agent_type=AgentType.COMMUNICATION)
    report = MultiAgentRuntime(agents=reg, tools=tools, permissions=PERMS).run(_graph([node]))
    assert not report.ok
    assert any(e.type == "APPROVAL_REQUIRED" for e in report.events)


# MA22: graph cycle detected (via validator, before execution)
def test_ma22_cycle_detected():
    from autoflow_ai.planning import PlannerOutput, validate_plan

    plan = PlannerOutput(
        normalized_goal="g",
        nodes=[
            PlanNode(task_id="a", objective="a", agent_type=AgentType.DOCUMENT, dependencies=("b",)),
            PlanNode(task_id="b", objective="b", agent_type=AgentType.DOCUMENT, dependencies=("a",)),
        ],
    )
    reasons = validate_plan(plan, known_agents={a.value for a in AgentType},
                            registered_tools=set(), available_capabilities=set(), granted_permissions=set())
    assert any("cycle" in r for r in reasons)


# MA23: planner output referencing unknown task
def test_ma23_unknown_task_reference():
    from autoflow_ai.planning import PlannerOutput, validate_plan

    plan = PlannerOutput(
        normalized_goal="g",
        nodes=[PlanNode(task_id="a", objective="a", agent_type=AgentType.DOCUMENT, dependencies=("ghost",))],
    )
    reasons = validate_plan(plan, known_agents={a.value for a in AgentType},
                            registered_tools=set(), available_capabilities=set(), granted_permissions=set())
    assert any("unknown task" in r for r in reasons)


# browser tool not registered in the runtime -> honest UNSUPPORTED, not fake success
def test_browser_agent_unsupported():
    # BrowserAgent is real, but no browser.* tools are registered here, so a
    # browser action is genuinely unavailable -> UNSUPPORTED -> failure.
    node = PlanNode(task_id="t_b", objective="browse", agent_type=AgentType.BROWSER,
                    parameters={"tool": "browser.navigate"})
    report = _runtime().run(_graph([node]))
    assert not report.ok
    assert report.graph.node("t_b").status == NodeStatus.FAILED


# deadlock detection: a node depends on a non-succeeding node
def test_deadlock_detection():
    # t_b depends on t_a; force t_a to FAIL via a browser action with no
    # registered browser tool (genuine UNSUPPORTED), so t_b can never run.
    nodes = [
        PlanNode(task_id="t_a", objective="a", agent_type=AgentType.BROWSER,
                 parameters={"tool": "browser.navigate"}),
        PlanNode(task_id="t_b", objective="b", agent_type=AgentType.RESEARCH, dependencies=("t_a",)),
    ]
    report = _runtime(max_replans=0).run(_graph(nodes))
    assert not report.ok
    # t_b must be blocked/cancelled, never executed
    assert report.graph.node("t_b").status in (NodeStatus.BLOCKED, NodeStatus.CANCELLED)


# concurrency: many independent nodes, no duplicate execution / races
def test_concurrency_no_duplicate_execution():
    counter = {"n": 0}
    lock = threading.Lock()

    class CountingAgent(SpecialistAgent):
        agent_type = AgentType.RESEARCH
        capabilities = ("research",)

        def propose(self, context):
            with lock:
                counter["n"] += 1
            time.sleep(0.001)
            return AgentResult(status=AgentStatus.OK, output={"i": context.task_id})

    reg = AgentRegistry()
    reg.register(CountingAgent())
    nodes = [PlanNode(task_id=f"t_{i}", objective=str(i), agent_type=AgentType.RESEARCH) for i in range(20)]
    report = _runtime(agents=reg, max_concurrency=8).run(_graph(nodes))
    assert report.ok
    assert counter["n"] == 20  # each node executed exactly once
    assert all(n.status == NodeStatus.SUCCEEDED for n in report.graph.nodes)


# long dependency chain
def test_long_dependency_chain():
    nodes = []
    for i in range(20):
        deps = (f"t_{i-1}",) if i else ()
        nodes.append(PlanNode(task_id=f"t_{i}", objective=str(i), agent_type=AgentType.RESEARCH, dependencies=deps))
    report = _runtime().run(_graph(nodes))
    assert report.ok
    assert all(n.status == NodeStatus.SUCCEEDED for n in report.graph.nodes)


# events are serializable and secret-free
def test_events_serializable():
    node = PlanNode(task_id="t_r", objective="r", agent_type=AgentType.RESEARCH)
    report = _runtime().run(_graph([node]))
    trace = report.trace()
    import json

    json.dumps(trace)  # must not raise
    assert all("api_key" not in str(e).lower() for e in trace)
