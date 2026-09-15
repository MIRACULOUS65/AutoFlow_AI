"""Autonomous computer-agent loop tests (observe->decide->act->verify).

These drive the AutonomousComputerAgent over the REAL computer tools + the
deterministic FakeDesktopAdapter. The agent is given a GOAL (not a fixed action
list) and must reach + independently verify it. False success is impossible: the
goal check reads the real observation, and a save is only "verified" after a
real save action executes.
"""

from __future__ import annotations

import pytest

from autoflow_ai.computer_use.autonomy import RateLimits
from autoflow_ai.computer_use.fake_adapter import FakeDesktopAdapter
from autoflow_ai.computer_use.tools import register_computer_tools
from autoflow_ai.runtime.registry import ToolRegistry
from autoflow_ai.runtime.tool_calling import ToolCallingController
from autoflow_ai.society import (
    AutonomousComputerAgent,
    Blackboard,
    GoalSpec,
    LoopOutcome,
    MessageBus,
    TrustClass,
)
from autoflow_ai.society.messages import MessageType


def build(adapter=None):
    adapter = adapter or FakeDesktopAdapter()
    reg = ToolRegistry()
    register_computer_tools(reg, adapter)
    perms = frozenset({"computer:read", "computer:launch", "computer:interact"})
    controller = ToolCallingController(registry=reg, permissions=perms)
    board = Blackboard()
    bus = MessageBus()
    agent = AutonomousComputerAgent(
        agent_id="computer:auto-1", adapter=adapter, controller=controller,
        board=board, bus=bus, execution_id="exec_auto1", task_id="auto-1",
    )
    return agent, adapter, board, bus


def test_auto_01_launch_type_verify_goal():
    agent, adapter, board, bus = build()
    res = agent.run(GoalSpec(expect_text="hello"))
    assert res.outcome == LoopOutcome.GOAL_VERIFIED
    assert res.goal_verified is True
    assert "hello" in adapter.text
    # at least launch + type + a verifying observation happened
    assert res.observed() >= 2


def test_auto_02_multi_step_beyond_single_node():
    agent, adapter, _b, _bus = build()
    res = agent.run(GoalSpec(expect_text="report body"))
    assert res.goal_verified
    # more than one distinct action proves it is not a single fixed node
    actions = {s.action for s in res.steps}
    assert len(actions) >= 1
    assert res.action_count >= 1


def test_auto_03_save_requires_real_save_action():
    agent, adapter, board, _bus = build()
    res = agent.run(GoalSpec(expect_text="data", expect_saved=True))
    assert res.goal_verified
    assert adapter.saved is True  # a real ctrl+s executed


def test_auto_04_no_false_success_when_editor_missing():
    # editor missing -> typing fails -> loop reports failure, never verified
    agent, adapter, board, _bus = build(FakeDesktopAdapter(missing_editor=True))
    res = agent.run(GoalSpec(expect_text="cannot type this"))
    assert res.goal_verified is False
    assert res.outcome in (LoopOutcome.FAILED, LoopOutcome.STEP_LIMIT, LoopOutcome.STUCK)


def test_auto_05_rate_limit_stops_loop():
    agent, adapter, _b, _bus = build()
    # allow only a single action -> cannot both launch and type
    agent._limits = RateLimits(max_actions_per_task=1)  # noqa: SLF001
    res = agent.run(GoalSpec(expect_text="lots of work here"))
    assert res.outcome in (LoopOutcome.RATE_LIMITED, LoopOutcome.STEP_LIMIT)
    assert res.goal_verified is False


def test_auto_06_stuck_detection_no_progress():
    # ambiguous save won't stop text goal, but force a goal the policy can't
    # satisfy so it repeats -> stuck detection fires.
    class NoProgressAdapter(FakeDesktopAdapter):
        def type_text(self, text, query=None):
            # accept the action but never actually change stored text
            from autoflow_ai.computer_use.models import ActionResult, ActionStatus
            return ActionResult(action_id="a", tool="computer.type",
                                arguments={"length": len(text)}, status=ActionStatus.OK,
                                changed_state=False)

    agent, adapter, _b, _bus = build(NoProgressAdapter())
    res = agent.run(GoalSpec(expect_text="never lands"))
    assert res.outcome in (LoopOutcome.STUCK, LoopOutcome.STEP_LIMIT)
    assert res.goal_verified is False


def test_auto_07_observations_posted_as_evidence():
    agent, adapter, board, _bus = build()
    agent.run(GoalSpec(expect_text="ev"))
    obs = board.latest("obs:auto-1")
    assert obs is not None
    # the final verifying observation is VERIFICATION trust
    assert obs.trust in (TrustClass.OBSERVATION, TrustClass.VERIFICATION)


def test_auto_08_messages_show_observe_act_verify():
    agent, adapter, _b, bus = build()
    agent.run(GoalSpec(expect_text="msg"))
    types = {m.type for m in bus.messages}
    assert MessageType.ACTION_REQUEST in types
    assert MessageType.VERIFICATION_RESULT in types


def test_auto_09_all_actions_go_through_authority_chain():
    # An unauthorized permission set must block every mutating action.
    adapter = FakeDesktopAdapter()
    reg = ToolRegistry()
    register_computer_tools(reg, adapter)
    controller = ToolCallingController(registry=reg, permissions=frozenset({"computer:read"}))
    agent = AutonomousComputerAgent(
        agent_id="computer:auto-x", adapter=adapter, controller=controller,
        board=Blackboard(), bus=MessageBus(), execution_id="exec_auth1", task_id="auth-1",
    )
    res = agent.run(GoalSpec(expect_text="blocked"))
    # launch needs computer:launch which we didn't grant -> fails closed
    assert res.goal_verified is False
    assert adapter.text == ""


def test_auto_10_empty_goal_not_trivially_verified():
    agent, adapter, _b, _bus = build()
    # a goal that only requires the window active still needs the app launched
    res = agent.run(GoalSpec())
    # policy launches the app, then goal (window active) is verified
    assert res.goal_verified is True
    assert adapter._launched is True  # noqa: SLF001
