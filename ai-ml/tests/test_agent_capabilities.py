"""Capability-routing tests for the real BrowserAgent and CommunicationAgent.

Each agent acts ONLY within its capability: it proposes its own tool family,
NOOPs when no tool is specified, and returns UNSUPPORTED (never a blind
passthrough) for a tool outside its capability. Supervisor.match routes to the
correct capable specialist.
"""

from __future__ import annotations

import pytest

from autoflow_ai.agents.models import AgentContext, AgentStatus
from autoflow_ai.agents.registry import build_default_registry
from autoflow_ai.agents.specialists import BrowserAutomationAgent, CommunicationAgent
from autoflow_ai.planning.models import AgentType, PlanNode
from autoflow_ai.society import MissionSupervisor


def ctx(tool=None, *, available=(), objective="do the thing"):
    params = {"tool": tool} if tool else {}
    return AgentContext(
        execution_id="exec_cap1", task_id="cap-1", tenant_id="org_local",
        workspace_id="ws_local", actor="user_local", objective=objective,
        parameters=params, available_tools=frozenset(available),
    )


# -- BrowserAgent -----------------------------------------------------------

def test_cap_01_browser_agent_capabilities():
    a = BrowserAutomationAgent()
    assert a.supports("browser_automation")
    assert a.supports("web_navigation")


def test_cap_02_browser_proposes_browser_tool():
    a = BrowserAutomationAgent()
    res = a.propose(ctx("browser.navigate", available=("browser.navigate",)))
    assert res.status == AgentStatus.OK
    assert res.proposed_action.tool_name == "browser.navigate"


def test_cap_03_browser_noop_without_tool():
    res = BrowserAutomationAgent().propose(ctx())
    assert res.status == AgentStatus.NOOP


def test_cap_04_browser_rejects_foreign_tool():
    # a document tool is outside the browser agent's capability
    res = BrowserAutomationAgent().propose(ctx("document.edit", available=("document.edit",)))
    assert res.status == AgentStatus.UNSUPPORTED
    assert res.proposed_action is None


def test_cap_05_browser_unsupported_when_tool_unregistered():
    res = BrowserAutomationAgent().propose(ctx("browser.navigate", available=()))
    assert res.status == AgentStatus.UNSUPPORTED


# -- CommunicationAgent -----------------------------------------------------

def test_cap_06_communication_agent_capabilities():
    a = CommunicationAgent()
    assert a.supports("communication") and a.supports("email")


def test_cap_07_communication_proposes_gmail_tool():
    res = CommunicationAgent().propose(ctx("gmail.compose", available=("gmail.compose",)))
    assert res.status == AgentStatus.OK
    assert res.proposed_action.tool_name == "gmail.compose"


def test_cap_08_communication_send_requires_verification():
    res = CommunicationAgent().propose(ctx("gmail.send", available=("gmail.send",)))
    assert res.status == AgentStatus.OK
    assert res.verification_needed is True


def test_cap_09_communication_rejects_foreign_tool():
    res = CommunicationAgent().propose(ctx("computer.click", available=("computer.click",)))
    assert res.status == AgentStatus.UNSUPPORTED
    assert res.proposed_action is None


def test_cap_10_communication_noop_without_tool():
    assert CommunicationAgent().propose(ctx()).status == AgentStatus.NOOP


# -- supervisor capability routing ------------------------------------------

def _sup():
    from autoflow_ai.runtime.registry import ToolRegistry
    from autoflow_ai.runtime.tool_calling import ToolCallingController

    return MissionSupervisor(
        registry=build_default_registry(),
        controller=ToolCallingController(registry=ToolRegistry(), permissions=frozenset()),
    )


def test_cap_11_supervisor_routes_browser_capability():
    node = PlanNode(task_id="b-1", objective="navigate", agent_type=AgentType.BROWSER,
                    required_capabilities=("browser_automation",),
                    parameters={"tool": "browser.navigate"})
    assert _sup().match(node) == AgentType.BROWSER


def test_cap_12_supervisor_routes_communication_capability():
    node = PlanNode(task_id="c-1", objective="email", agent_type=AgentType.COMMUNICATION,
                    required_capabilities=("email",), parameters={"tool": "gmail.compose"})
    assert _sup().match(node) == AgentType.COMMUNICATION


def test_cap_13_supervisor_no_agent_for_unknown_capability():
    node = PlanNode(task_id="x-1", objective="x", agent_type=AgentType.BROWSER,
                    required_capabilities=("teleportation",), parameters={})
    assert _sup().match(node) is None


def test_cap_14_browser_agent_registered_in_default_registry():
    reg = build_default_registry()
    agent = reg.get(AgentType.BROWSER)
    assert agent is not None
    assert "browser_automation" in agent.capabilities  # no longer an empty stub


def test_cap_15_communication_agent_registered_with_email():
    reg = build_default_registry()
    agent = reg.get(AgentType.COMMUNICATION)
    assert agent is not None and "email" in agent.capabilities
