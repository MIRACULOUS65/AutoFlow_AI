"""CollaborativeAgent: a real per-agent internal loop over the substrate.

The base multi-agent runtime executed exactly one node per agent (a fixed
step). A CollaborativeAgent instead runs its own bounded state machine:

    OBSERVE -> ASSESS -> DECIDE_NEXT -> PROPOSE -> (runtime executes) ->
    CONSUME_RESULT -> VERIFY_PROGRESS -> DECIDE_CONTINUE

It never executes tools itself. It PROPOSES an action; the injected
ToolCallingController runs it (authorization + policy + execution). It never
declares its own success as fact — it produces a DecisionSummary with a
`done_claim`, and an independent critic decides. Every turn emits an
AgentMessage and posts structured results (never raw CoT) to the blackboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..agents.base import SpecialistAgent
from ..agents.models import AgentContext, AgentResult, AgentStatus
from ..runtime.tool_calling import ToolCallingController
from ..schemas.enums import StrEnum
from .blackboard import Blackboard, BlackboardEntry, TrustClass
from .messages import AgentMessage, MessageBus, MessageType
from .roles import AgentRole, DecisionKind, DecisionSummary


class AgentPhase(StrEnum):
    OBSERVE = "observe"
    ASSESS = "assess"
    DECIDE_NEXT = "decide_next"
    PROPOSE = "propose"
    CONSUME_RESULT = "consume_result"
    VERIFY_PROGRESS = "verify_progress"
    DECIDE_CONTINUE = "decide_continue"
    DONE = "done"
    BLOCKED = "blocked"


def _mid(execution_id: str, agent_id: str, n: int) -> str:
    # message ids need only be unique + short; not prefix-validated
    return f"{agent_id}-{n}-{execution_id[-6:]}"


@dataclass
class AgentTurn:
    """One iteration of the internal loop, for the agenticity trace."""

    phase: str
    decision: DecisionSummary
    tool_ok: bool | None = None
    observation: str = ""


@dataclass
class WorkerRun:
    agent_id: str
    role_name: str
    task_id: str
    turns: list[AgentTurn] = field(default_factory=list)
    outputs: dict = field(default_factory=dict)
    done_claim: bool = False
    blocked: bool = False
    handoff_to: str | None = None
    iterations: int = 0

    def observation_count(self) -> int:
        return sum(1 for t in self.turns if t.observation)

    def acted(self) -> bool:
        return any(t.tool_ok is not None for t in self.turns)


class CollaborativeAgent:
    """Wraps a SpecialistAgent in a real internal reasoning/acting loop."""

    def __init__(
        self,
        *,
        agent_id: str,
        role: AgentRole,
        specialist: SpecialistAgent,
        controller: ToolCallingController,
        board: Blackboard,
        bus: MessageBus,
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self._specialist = specialist
        self._controller = controller
        self._board = board
        self._bus = bus
        self._msg_n = 0

    # -- messaging -------------------------------------------------------
    def _emit(self, recipient: str, mtype: MessageType, context: AgentContext, **kw) -> None:
        self._msg_n += 1
        msg = AgentMessage(
            message_id=_mid(context.execution_id, self.agent_id, self._msg_n),
            execution_id=context.execution_id,
            sender=self.agent_id,
            recipient=recipient,
            type=mtype,
            task_id=context.task_id,
            objective=context.objective,
            **kw,
        )
        self._bus.send(msg)

    # -- the internal loop ----------------------------------------------
    def run(self, context: AgentContext, *, supervisor_id: str = "supervisor") -> WorkerRun:
        run = WorkerRun(agent_id=self.agent_id, role_name=self.role.name, task_id=context.task_id)
        self._emit(supervisor_id, MessageType.TASK_ACCEPTED, context, summary=f"accepted {context.task_id}")

        working_ctx = context
        for _ in range(self.role.max_iterations):
            run.iterations += 1

            # OBSERVE + ASSESS + DECIDE_NEXT + PROPOSE are produced by the
            # specialist as one structured decision (its "brain" turn).
            result = self._specialist.propose(working_ctx)
            decision = self._to_decision(result)
            turn = AgentTurn(phase=AgentPhase.DECIDE_NEXT, decision=decision)

            if decision.kind == DecisionKind.BLOCKED or result.status in (
                AgentStatus.UNSUPPORTED,
                AgentStatus.FAILED,
            ):
                run.blocked = True
                turn.phase = AgentPhase.BLOCKED
                run.turns.append(turn)
                self._emit(
                    supervisor_id, MessageType.BLOCKED, context,
                    summary=decision.reasoning_summary or "blocked",
                    confidence=decision.confidence,
                )
                break

            if decision.kind == DecisionKind.REQUEST_HANDOFF and result:
                run.handoff_to = str(decision.handoff_to) if decision.handoff_to else None
                turn.phase = AgentPhase.DECIDE_CONTINUE
                run.turns.append(turn)
                self._emit(
                    supervisor_id, MessageType.HANDOFF, context,
                    summary=f"handoff to {run.handoff_to}",
                    requested_capability=(decision.needs[0] if decision.needs else None),
                )
                break

            # PROPOSE -> runtime executes (only path to side effects)
            if decision.kind == DecisionKind.PROPOSE_ACTION and result.proposed_action is not None:
                turn.phase = AgentPhase.PROPOSE
                self._emit(
                    supervisor_id, MessageType.ACTION_REQUEST, context,
                    summary=f"propose {result.proposed_action.tool_name}",
                    payload={"tool": result.proposed_action.tool_name},
                )
                tool_result, _trace = self._controller.call(
                    tool_name=result.proposed_action.tool_name,
                    arguments=result.proposed_action.tool_args,
                    execution_id=context.execution_id,
                    step_id=_step_id(context.task_id),
                    reason=decision.reasoning_summary,
                )
                turn.phase = AgentPhase.CONSUME_RESULT
                turn.tool_ok = tool_result.ok
                turn.observation = _observe(tool_result)
                run.turns.append(turn)

                if not tool_result.ok:
                    # VERIFY_PROGRESS: no progress -> report failure, stop.
                    self._emit(
                        supervisor_id, MessageType.FAILURE, context,
                        summary=f"tool failed: {tool_result.error_type}",
                        confidence=0.0,
                    )
                    run.blocked = True
                    break

                # progress observed -> record the REAL tool execution as
                # TOOL_RESULT evidence (data the critic can verify against),
                # plus an AGENT claim entry summarizing it.
                out = tool_result.output or {}
                run.outputs[context.task_id] = out
                self._post_tool_result(context, tool_result, summary=turn.observation)
                self._post_result(context, summary=turn.observation, value=out,
                                   confidence=decision.confidence)
                # One verified action per subtask node is the substrate contract;
                # claim done (critic decides truth).
                run.done_claim = True
                self._emit(
                    supervisor_id, MessageType.RESULT, context,
                    summary=turn.observation, confidence=decision.confidence,
                    output_refs=(f"{context.task_id}",),
                )
                break

            # PRODUCE_OUTPUT: structured output with no side effect
            if decision.kind in (DecisionKind.PRODUCE_OUTPUT, DecisionKind.CLAIM_DONE):
                turn.phase = AgentPhase.VERIFY_PROGRESS
                run.turns.append(turn)
                run.outputs[context.task_id] = result.output
                run.done_claim = True
                self._post_result(context, summary=decision.reasoning_summary,
                                  value=result.output, confidence=decision.confidence)
                self._emit(
                    supervisor_id, MessageType.RESULT, context,
                    summary=decision.reasoning_summary or "produced output",
                    confidence=decision.confidence, output_refs=(f"{context.task_id}",),
                )
                break

            # NOOP / nothing actionable -> stop honestly, not fake-done
            run.turns.append(turn)
            if result.status == AgentStatus.NOOP:
                self._emit(supervisor_id, MessageType.BLOCKED, context, summary="no action available")
                run.blocked = True
                break

        return run

    # -- helpers ---------------------------------------------------------
    def _to_decision(self, result: AgentResult) -> DecisionSummary:
        if result.status == AgentStatus.UNSUPPORTED:
            kind = DecisionKind.BLOCKED
        elif result.status == AgentStatus.FAILED:
            kind = DecisionKind.BLOCKED
        elif result.status == AgentStatus.NOOP:
            kind = DecisionKind.BLOCKED
        elif result.proposed_action is not None:
            kind = DecisionKind.PROPOSE_ACTION
        else:
            kind = DecisionKind.PRODUCE_OUTPUT
        return DecisionSummary(
            agent_id=self.agent_id,
            role=self.role.name,
            kind=kind,
            reasoning_summary=result.reasoning_summary,
            proposed_tool=result.proposed_action.tool_name if result.proposed_action else None,
            proposed_args=result.proposed_action.tool_args if result.proposed_action else {},
            output=result.output,
            done_claim=result.status == AgentStatus.OK,
            confidence=result.confidence,
            warnings=result.warnings,
        )

    def _post_result(self, context: AgentContext, *, summary: str, value: dict, confidence: float) -> None:
        self._board.post(
            BlackboardEntry(
                key=f"result:{context.task_id}",
                value=value if isinstance(value, dict) else {"value": value},
                summary=summary[:1024],
                trust=TrustClass.AGENT,
                producer=self.agent_id,
                task_id=context.task_id,
                confidence=confidence,
            )
        )

    def _post_tool_result(self, context: AgentContext, tool_result, *, summary: str) -> None:
        """Post the real tool execution outcome as TOOL_RESULT evidence.

        This is not the agent's *claim*; it is the observable result of a real
        execution through the authority chain, which the critic verifies
        against. It carries ``ok`` so a failed execution reads as data, never
        as a success.
        """

        out = tool_result.output or {}
        value = {"ok": bool(tool_result.ok), "tool": tool_result.tool_name}
        if isinstance(out, dict):
            value.update({k: v for k, v in out.items() if not isinstance(v, (bytes, bytearray))})
        self._board.post(
            BlackboardEntry(
                key=f"tool:{context.task_id}",
                value=value,
                summary=summary[:1024],
                trust=TrustClass.TOOL_RESULT,
                producer=self.agent_id,
                task_id=context.task_id,
                confidence=1.0 if tool_result.ok else 0.0,
            )
        )


def _step_id(task_id: str) -> str:
    # produce a schema-valid step id (prefix 'step_') from a task id
    token = "".join(c for c in task_id if c.isalnum() or c == "-") or "x"
    return f"step_{token[:60]}"


def _observe(tool_result) -> str:
    if not tool_result.ok:
        return f"tool {tool_result.tool_name} failed: {tool_result.error_type}"
    out = tool_result.output or {}
    keys = ", ".join(sorted(out)[:6])
    return f"{tool_result.tool_name} ok; outputs: {keys}" if keys else f"{tool_result.tool_name} ok"
