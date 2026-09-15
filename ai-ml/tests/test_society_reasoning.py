"""Real-model reasoning path tests (fail-closed, deterministic fallback).

A fake router stands in for the ModelRouter so these stay hermetic. The point
is to prove the model can only ever PROPOSE, that every malformed/hallucinated/
off-role/erroring output fails closed to the deterministic specialist, and that
enabling the model never produces false success.
"""

from __future__ import annotations

import pytest

from autoflow_ai.agents.models import AgentContext, AgentStatus
from autoflow_ai.agents.specialists import DocumentAgent
from autoflow_ai.planning.models import AgentType
from autoflow_ai.schemas.models import ModelResponse, ModelUsage
from autoflow_ai.society.reasoning import ModelDecision, ReasoningPolicy
from autoflow_ai.society.roles import role_for

from tests.test_society import (
    build_registry_with_note_tool, make_controller, doc_node, graph,
)
from autoflow_ai.agents.registry import build_default_registry
from autoflow_ai.society import MissionSupervisor, MissionLimits
from autoflow_ai.society.supervisor import MissionOutcome


class FakeRouter:
    """Returns a canned ModelResponse or raises, for fail-closed testing."""

    def __init__(self, *, structured=None, text=None, raises=False):
        self._structured = structured
        self._text = text
        self._raises = raises
        self.calls = 0

    def generate(self, request, prompt):
        self.calls += 1
        if self._raises:
            raise RuntimeError("model timeout")
        return ModelResponse(
            request_id="mreq_society", model_id="model_fake", provider="fake",
            finish_reason="stop", text=self._text, structured_output=self._structured,
            usage=ModelUsage(input_tokens=1, output_tokens=1),
        )


def ctx(tools=("document.edit",)):
    return AgentContext(
        execution_id="exec_r1", task_id="doc-1", tenant_id="org_m",
        workspace_id="ws_m", actor="user_m", objective="replace foo with bar",
        parameters={"tool": "document.edit", "prompt": "replace foo with bar"},
        available_tools=frozenset(tools),
    )


def policy(router):
    return ReasoningPolicy(router=router, role=role_for(AgentType.DOCUMENT),
                           deterministic=DocumentAgent())


def test_reason_01_valid_model_proposal_used():
    router = FakeRouter(structured={"action": "propose_action", "tool": "document.edit",
                                    "tool_args": {"operations": []},
                                    "reasoning_summary": "edit it", "confidence": 0.8})
    res = policy(router).decide(ctx())
    assert res.status == AgentStatus.OK
    assert res.proposed_action.tool_name == "document.edit"
    assert router.calls == 1


def test_reason_02_no_router_uses_deterministic():
    res = ReasoningPolicy(router=None, role=role_for(AgentType.DOCUMENT),
                          deterministic=DocumentAgent()).decide(ctx())
    assert res.status in (AgentStatus.OK, AgentStatus.NOOP)


def test_reason_03_router_error_fails_closed():
    router = FakeRouter(raises=True)
    res = policy(router).decide(ctx())
    # falls back to the deterministic document proposal
    assert res.status == AgentStatus.OK
    assert res.proposed_action is not None


def test_reason_04_malformed_output_fails_closed():
    router = FakeRouter(text="not json at all, just prose")
    res = policy(router).decide(ctx())
    assert res.proposed_action is not None  # deterministic fallback


def test_reason_05_hallucinated_tool_rejected():
    router = FakeRouter(structured={"action": "propose_action", "tool": "does.not_exist",
                                    "confidence": 0.9})
    res = policy(router).decide(ctx())
    # hallucinated tool -> reject model decision -> deterministic fallback tool
    assert res.proposed_action.tool_name == "document.edit"


def test_reason_06_off_role_tool_rejected():
    # computer.* is not allowed for the document role
    router = FakeRouter(structured={"action": "propose_action", "tool": "computer.click",
                                    "confidence": 0.9})
    res = policy(router).decide(ctx(tools=("document.edit", "computer.click")))
    assert res.proposed_action.tool_name == "document.edit"


def test_reason_07_blocked_action_reported():
    router = FakeRouter(structured={"action": "blocked", "reasoning_summary": "cannot"})
    res = policy(router).decide(ctx())
    assert res.status == AgentStatus.FAILED


def test_reason_08_model_cannot_execute_only_propose():
    # The decision path returns an AgentResult with a PROPOSAL; it never calls a tool.
    router = FakeRouter(structured={"action": "propose_action", "tool": "document.edit",
                                    "tool_args": {"operations": []}, "confidence": 0.7})
    res = policy(router).decide(ctx())
    assert res.proposed_action is not None  # a proposal, not an execution result


def test_reason_09_mission_with_router_still_verified_no_false_success():
    reg = build_registry_with_note_tool()
    router = FakeRouter(structured={"action": "propose_action", "tool": "document.edit",
                                    "tool_args": {"operations": []}, "confidence": 0.8})
    sup = MissionSupervisor(registry=build_default_registry(),
                            controller=make_controller(reg), router=router,
                            limits=MissionLimits())
    report = sup.run(graph([doc_node()]))
    assert report.outcome == MissionOutcome.COMPLETE
    m = sup.metrics(report)
    assert m.false_success == 0
    assert router.calls >= 1  # the model was actually consulted


def test_reason_10_mission_with_broken_router_still_safe():
    # A model that always errors must not break the mission — it fails closed
    # to deterministic proposals and still verifies via the real tool + critic.
    reg = build_registry_with_note_tool()
    sup = MissionSupervisor(registry=build_default_registry(),
                            controller=make_controller(reg), router=FakeRouter(raises=True),
                            limits=MissionLimits())
    report = sup.run(graph([doc_node()]))
    assert report.outcome == MissionOutcome.COMPLETE
    assert sup.metrics(report).false_success == 0
