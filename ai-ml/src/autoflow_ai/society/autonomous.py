"""Autonomous computer/browser agent loops (beyond a single fixed node).

The Phase 6/7 agents proposed exactly ONE action per plan node. These loops are
genuinely autonomous: given a *goal state* (not a fixed action list), the agent
repeatedly OBSERVES the environment, DECIDES the single next action that reduces
the gap to the goal, PROPOSES it (executed only through the tool authority
chain), then VERIFIES the observed post-condition before deciding whether to
continue. It stops when the goal is verified, when stuck, or when a rate/step
limit is hit — never by faking success.

The decision policy here is deterministic and goal-directed (it inspects the
real observation and picks the next needed action). A real-model policy can be
plugged in via ``policy=`` without changing the loop or the safety envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from ..computer_use.autonomy import RateLimits, StuckDetector
from ..computer_use.models import ActionStatus, DesktopObservation, ElementQuery
from ..computer_use.observation import ObservationFusion, TargetResolver, ResolutionStatus
from ..runtime.tool_calling import ToolCallingController
from ..schemas.enums import StrEnum
from .blackboard import Blackboard, BlackboardEntry, TrustClass
from .messages import AgentMessage, MessageBus, MessageType


class LoopOutcome(StrEnum):
    GOAL_VERIFIED = "goal_verified"
    STUCK = "stuck"
    RATE_LIMITED = "rate_limited"
    STEP_LIMIT = "step_limit"
    FAILED = "failed"
    NO_ACTION = "no_action"


@dataclass
class GoalSpec:
    """A verifiable target state for an autonomous computer loop.

    * ``expect_text`` — substring that must appear in the editor value.
    * ``expect_saved`` — the document must be saved (via a real save action).
    * ``expect_window`` — this window title must be active.
    """

    expect_text: str | None = None
    expect_saved: bool = False
    expect_window: str | None = None


@dataclass
class LoopStep:
    index: int
    action: str
    status: str
    changed_state: bool
    state_hash: str
    observation_summary: str


@dataclass
class AutonomousResult:
    outcome: LoopOutcome
    steps: list[LoopStep] = field(default_factory=list)
    goal_verified: bool = False
    reason: str = ""

    @property
    def action_count(self) -> int:
        return sum(1 for s in self.steps if s.status is not None)

    def observed(self) -> int:
        return len(self.steps)


class DesktopLike(Protocol):  # pragma: no cover - structural typing
    def inspect_desktop(self) -> DesktopObservation: ...
    def launch_application(self, executable: str): ...
    def type_text(self, text: str, query: ElementQuery | None = None): ...
    def click(self, query: ElementQuery): ...
    def hotkey(self, *keys: str): ...


# A policy maps (goal, observation) -> (tool_name, args) or None when done.
Policy = Callable[[GoalSpec, DesktopObservation], tuple[str, dict] | None]


def default_desktop_policy(goal: GoalSpec, obs: DesktopObservation) -> tuple[str, dict] | None:
    """Deterministic goal-directed policy for a Notepad-like target.

    Chooses the single next action that reduces the gap to the goal:
    launch -> type missing text -> save. Returns None when the goal state is
    already reflected in the observation (the loop then verifies independently).
    """

    editor = next((e for e in obs.visible_elements if e.role == "edit"), None)
    launched = obs.active_window is not None

    # 1. ensure the app is open
    if not launched:
        return ("computer.launch_application", {"executable": "notepad.exe"})

    # 2. ensure required text is present
    if goal.expect_text is not None:
        current = (editor.value if editor and editor.value else "") if editor else ""
        if goal.expect_text not in current:
            missing = goal.expect_text
            if current and goal.expect_text.startswith(current):
                missing = goal.expect_text[len(current):]
            return ("computer.type", {"text": missing})

    # 3. ensure saved
    if goal.expect_saved:
        # we cannot read "saved" from the observation directly; the loop tracks
        # whether a save action has been issued+verified via state change.
        return ("computer.hotkey", {"keys": ["ctrl", "s"]})

    return None


class AutonomousComputerAgent:
    """Runs a real observe->decide->act->verify loop over a desktop adapter."""

    def __init__(
        self,
        *,
        agent_id: str,
        adapter: DesktopLike,
        controller: ToolCallingController,
        board: Blackboard,
        bus: MessageBus,
        execution_id: str,
        task_id: str,
        policy: Policy | None = None,
        rate_limits: RateLimits | None = None,
        max_steps: int = 12,
    ) -> None:
        self.agent_id = agent_id
        self._adapter = adapter
        self._controller = controller
        self._board = board
        self._bus = bus
        self._execution_id = execution_id
        self._task_id = task_id
        self._policy = policy or default_desktop_policy
        self._limits = rate_limits or RateLimits()
        self._max_steps = max_steps
        self._stuck = StuckDetector()
        self._fusion = ObservationFusion()
        self._resolver = TargetResolver()
        self._saved_confirmed = False

    def _emit(self, mtype: MessageType, summary: str, **kw) -> None:
        self._bus.send(
            AgentMessage(
                message_id=f"{self.agent_id}-{len(self._bus.messages)}-{self._execution_id[-5:]}",
                execution_id=self._execution_id, sender=self.agent_id,
                recipient="supervisor", type=mtype, task_id=self._task_id,
                summary=summary[:200], **kw,
            )
        )

    def run(self, goal: GoalSpec) -> AutonomousResult:
        result = AutonomousResult(outcome=LoopOutcome.FAILED)
        self._emit(MessageType.TASK_ACCEPTED, f"autonomous computer loop for {self._task_id}")

        for i in range(self._max_steps):
            # OBSERVE (real adapter)
            obs = self._adapter.inspect_desktop()
            state_hash = obs.state_hash

            # VERIFY goal first — completion is a verified fact, not a claim.
            if self._goal_met(goal, obs):
                result.goal_verified = True
                result.outcome = LoopOutcome.GOAL_VERIFIED
                self._post_observation(obs, verified=True)
                self._emit(MessageType.VERIFICATION_RESULT, "goal verified from observation",
                           confidence=0.95)
                return result

            # DECIDE next action (goal-directed policy over the observation)
            decision = self._policy(goal, obs)
            if decision is None:
                # policy says nothing to do but goal not verified -> honest stop
                result.outcome = LoopOutcome.NO_ACTION
                result.reason = "policy produced no action but goal not verified"
                self._post_observation(obs, verified=False)
                self._emit(MessageType.BLOCKED, result.reason)
                return result

            tool_name, args = decision
            action_key = f"{tool_name}:{sorted(args.items()) if isinstance(args, dict) else args}"

            # rate limit
            allowed, why = self._limits.allow_action()
            if not allowed:
                result.outcome = LoopOutcome.RATE_LIMITED
                result.reason = why
                self._emit(MessageType.BLOCKED, f"rate limited: {why}")
                return result

            # stuck detection (repeated state or repeated action = no progress)
            if self._stuck.record_state(state_hash) or self._stuck.record_action(action_key):
                result.outcome = LoopOutcome.STUCK
                result.reason = "no progress (repeated state/action)"
                self._emit(MessageType.BLOCKED, result.reason)
                return result

            # PROPOSE -> execute only through the authority chain
            self._emit(MessageType.ACTION_REQUEST, f"propose {tool_name}", payload={"tool": tool_name})
            tool_result, _trace = self._controller.call(
                tool_name=tool_name, arguments=args,
                execution_id=self._execution_id, step_id=_step_id(self._task_id, i),
                reason=f"advance toward goal ({tool_name})",
            )
            self._limits.record_action()

            # CONSUME + VERIFY PROGRESS via a fresh observation
            after = self._adapter.inspect_desktop()
            changed = after.state_hash != state_hash
            if tool_name == "computer.hotkey" and list(args.get("keys", [])) == ["ctrl", "s"]:
                # a save hotkey that executed ok is our save confirmation signal
                self._saved_confirmed = self._saved_confirmed or bool(tool_result.ok)

            step = LoopStep(
                index=i, action=tool_name,
                status=str(tool_result.ok),
                changed_state=changed, state_hash=after.state_hash,
                observation_summary=after.summary(max_elements=8),
            )
            result.steps.append(step)
            self._post_observation(after, verified=False)

            if not tool_result.ok:
                # a failed action is not progress; report and stop (supervisor
                # may reassign/replan — the loop itself does not fake recovery).
                result.outcome = LoopOutcome.FAILED
                result.reason = f"action failed: {tool_result.error_type}"
                self._emit(MessageType.FAILURE, result.reason, confidence=0.0)
                return result

        # exhausted steps: verify one last time honestly
        obs = self._adapter.inspect_desktop()
        if self._goal_met(goal, obs):
            result.goal_verified = True
            result.outcome = LoopOutcome.GOAL_VERIFIED
            self._post_observation(obs, verified=True)
            return result
        result.outcome = LoopOutcome.STEP_LIMIT
        result.reason = "max steps reached without verified goal"
        self._emit(MessageType.BLOCKED, result.reason)
        return result

    # -- verification (independent of the policy that acted) -------------
    def _goal_met(self, goal: GoalSpec, obs: DesktopObservation) -> bool:
        if goal.expect_window is not None:
            if (obs.active_window or "").lower().find(goal.expect_window.lower()) < 0:
                return False
        if goal.expect_text is not None:
            editor = next((e for e in obs.visible_elements if e.role == "edit"), None)
            value = (editor.value if editor and editor.value else "") if editor else ""
            if goal.expect_text not in value:
                return False
        if goal.expect_saved and not self._saved_confirmed:
            return False
        # require that we actually observed *something* (app open) to avoid
        # trivially-true empty goals.
        return obs.active_window is not None

    def _post_observation(self, obs: DesktopObservation, *, verified: bool) -> None:
        self._board.post(
            BlackboardEntry(
                key=f"obs:{self._task_id}",
                value={
                    "active_window": obs.active_window,
                    "state_hash": obs.state_hash,
                    "elements": len(obs.visible_elements),
                    "saved_confirmed": self._saved_confirmed,
                },
                summary=obs.summary(max_elements=6),
                trust=TrustClass.VERIFICATION if verified else TrustClass.OBSERVATION,
                producer=self.agent_id, task_id=self._task_id,
                confidence=0.95 if verified else 0.6,
            )
        )


def _step_id(task_id: str, i: int) -> str:
    token = "".join(c for c in task_id if c.isalnum() or c == "-") or "x"
    return f"step_{token[:54]}-{i}"
