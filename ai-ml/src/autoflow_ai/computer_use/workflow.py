"""WorkflowExecution: the autonomous observe -> act -> verify loop (CP6).

A first-class, serializable execution object that drives a bounded loop:

    observe -> goal satisfied? -> propose action -> validate/authorize
    -> (approval) -> execute via ToolCallingController -> observe again
    -> verify -> success | recover | replan | fail-safe

It enforces rate limits, stuck detection and the recovery ladder, and emits an
inspectable trace. Cleanup is the caller's responsibility (finally-style).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..runtime.tool_calling import ToolCallingController
from .autonomy import RateLimits, RecoveryEngine, RecoveryStep, StuckDetector


class WFStatus:
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"
    NEEDS_REPLAN = "needs_replan"
    TIMEOUT = "timeout"


@dataclass
class WFStep:
    tool: str
    args: dict
    goal_check: str = ""  # optional: a text/state marker signalling done


@dataclass
class WorkflowExecution:
    execution_id: str
    goal: str
    steps: list[WFStep]
    status: str = WFStatus.RUNNING
    trace: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    recovery_events: list[str] = field(default_factory=list)
    final_result: dict = field(default_factory=dict)

    def _emit(self, event: str, **data) -> None:
        self.trace.append({"event": event, **data})

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "goal": self.goal,
            "status": self.status,
            "steps": [{"tool": s.tool} for s in self.steps],
            "trace": self.trace,
            "recovery_events": self.recovery_events,
            "final_result": self.final_result,
        }


class AutonomyLoop:
    """Runs a WorkflowExecution's steps with observe/act/verify + recovery."""

    def __init__(
        self,
        *,
        controller: ToolCallingController,
        observe,               # callable() -> state_hash (str)
        verify=None,           # callable(step, before, after, result) -> bool
        limits: RateLimits | None = None,
    ) -> None:
        self._controller = controller
        self._observe = observe
        self._verify = verify
        self._limits = limits or RateLimits()

    def run(self, wf: WorkflowExecution) -> WorkflowExecution:
        stuck = StuckDetector()
        for step in wf.steps:
            allowed, reason = self._limits.allow_action()
            if not allowed:
                wf.status = WFStatus.TIMEOUT
                wf._emit("RATE_LIMIT", detail=reason)
                return wf

            recovery = RecoveryEngine(max_steps=3)
            while True:
                before = self._observe()
                wf._emit("OBSERVED", state=before[:12])

                result, tr = self._controller.call(
                    tool_name=step.tool, arguments=step.args,
                    execution_id=wf.execution_id, step_id="step_auto",
                )
                self._limits.record_action()
                wf.tool_results.append(tr)
                wf._emit("ACTION_EXECUTED", tool=step.tool, ok=result.ok)

                after = self._observe()
                wf._emit("OBSERVED_AFTER", state=after[:12])

                ok = result.ok
                if ok and self._verify is not None:
                    ok = self._verify(step, before, after, result)
                    wf._emit("VERIFIED" if ok else "VERIFY_FAILED", tool=step.tool)

                if ok:
                    break

                # stuck detection
                if stuck.record_state(after) or stuck.record_action(f"{step.tool}"):
                    wf.status = WFStatus.NEEDS_REPLAN
                    wf._emit("STUCK", tool=step.tool)
                    return wf

                nxt = recovery.next_step()
                wf.recovery_events.append(f"{step.tool}:{nxt}")
                wf._emit("RECOVER", step=str(nxt), tool=step.tool)
                if nxt == RecoveryStep.FAIL_SAFE or recovery.exhausted:
                    wf.status = WFStatus.FAILED
                    wf._emit("FAIL_SAFE", tool=step.tool, reason=result.error_message or "verify failed")
                    return wf
                # RETRY / RE_OBSERVE loop again (bounded by recovery.max_steps)

        wf.status = WFStatus.SUCCESS
        wf._emit("COMPLETE")
        return wf
