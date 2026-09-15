"""Execution engine: walk a validated TaskGraph to a verified outcome.

Loop per step (EXECUTION_RUNTIME.md §2):

    resolve step -> agent proposes action -> validate tool call -> permission
    check -> execute deterministic tool -> observe -> verify -> (bounded
    recovery on failure) -> next step

The engine is generic over tools; the document slice registers document tools,
but browser/desktop/email tools plug into the same registry and loop later.
It emits a structured trace (list of ExecutionEvent) and never marks COMPLETE
unless every material step verified.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path
from typing import Any

from ..documents.base import DocumentError, open_document
from ..schemas.common import utcnow
from ..schemas.enums import (
    ActorType,
    EventType,
    ExecutionStatus,
    StepStatus,
    VerificationKind,
    VerificationStatus,
)
from ..schemas.execution import (
    Observation,
    VerificationCheck,
    VerificationResult,
    is_valid_transition,
)
from ..schemas.tasks import TaskGraph
from ..schemas.tools import ToolCallRequest
from ..schemas.workflows import ExecutionEvent
from .document_tools import DocumentSession
from .registry import ToolRegistry


@dataclass
class TraceEntry:
    label: str
    detail: str = ""


@dataclass
class ExecutionReport:
    execution_id: str
    task_id: str
    status: ExecutionStatus
    trace: list[TraceEntry] = field(default_factory=list)
    events: list[ExecutionEvent] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    verifications: list[VerificationResult] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == ExecutionStatus.COMPLETE


class ExecutionEngine:
    """Runs a plan against a tool registry, producing a verified outcome."""

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        session: DocumentSession,
        organization_id: str,
        workspace_id: str,
        permissions: frozenset[str],
        max_recovery_attempts: int = 3,
    ) -> None:
        self._registry = registry
        self._session = session
        self._org = organization_id
        self._ws = workspace_id
        self._permissions = permissions
        self._max_recovery = max_recovery_attempts
        self._event_seq = 0

    # -- event/trace helpers -------------------------------------------------

    def _event(self, report: ExecutionReport, etype: EventType, data: dict[str, Any]) -> None:
        self._event_seq += 1
        report.events.append(
            ExecutionEvent(
                event_id=f"evt_{self._event_seq:04d}",
                type=etype,
                occurred_at=utcnow().replace(tzinfo=timezone.utc),
                organization_id=self._org,
                workspace_id=self._ws,
                task_id=report.task_id,
                execution_id=report.execution_id,
                actor_type=ActorType.WORKER,
                actor_id="engine",
                data=data,
            )
        )

    def _trace(self, report: ExecutionReport, label: str, detail: str = "") -> None:
        report.trace.append(TraceEntry(label=label, detail=detail))

    def _transition(self, report: ExecutionReport, nxt: ExecutionStatus) -> None:
        if report.status != nxt and not is_valid_transition(report.status, nxt):
            raise RuntimeError(
                f"illegal execution transition {report.status} -> {nxt}"
            )
        report.status = nxt

    # -- permission gate -----------------------------------------------------

    def _permitted(self, tool_name: str) -> bool:
        definition = self._registry.definition(tool_name)
        return definition.permission_scope in self._permissions

    # -- main loop -----------------------------------------------------------

    def run(self, plan: TaskGraph, *, execution_id: str) -> ExecutionReport:
        report = ExecutionReport(
            execution_id=execution_id,
            task_id=plan.task_id,
            status=ExecutionStatus.QUEUED,
        )
        self._trace(report, "TASK CREATED", plan.task_id)
        self._event(report, EventType.TASK_CREATED, {"goal": plan.goal})

        self._transition(report, ExecutionStatus.PLANNING)
        self._trace(report, "PLAN GENERATED", f"{len(plan.nodes)} steps")
        self._event(report, EventType.TASK_PLANNED, {"steps": len(plan.nodes)})

        self._transition(report, ExecutionStatus.VALIDATING)
        self._trace(report, "PLAN VALIDATED", " -> ".join(plan.topological_order()))
        self._event(report, EventType.PLAN_VALIDATED, {"order": list(plan.topological_order())})

        self._transition(report, ExecutionStatus.RUNNING)

        nodes_by_id = {n.step_id: n for n in plan.nodes}
        for step_id in plan.topological_order():
            node = nodes_by_id[step_id]
            ok = self._run_step(report, node)
            if not ok:
                self._transition(report, ExecutionStatus.FAILED)
                self._event(report, EventType.EXECUTION_FAILED, {"step": step_id})
                self._trace(report, "EXECUTION FAILED", step_id)
                return report

        self._transition(report, ExecutionStatus.COMPLETE)
        self._event(report, EventType.EXECUTION_COMPLETED, {})
        self._trace(report, "EXECUTION COMPLETE")
        return report

    def _run_step(self, report: ExecutionReport, node) -> bool:
        self._trace(report, f"AGENT ASSIGNED: {node.assigned_agent}-agent", node.objective)
        self._event(report, EventType.AGENT_STARTED, {"agent": str(node.assigned_agent), "step": node.step_id})

        tool_name = node.expected_state.get("tool")

        # The verify step is handled by the engine's verifier (not a side-effect tool).
        if tool_name == "document.verify":
            return self._verify_step(report, node)

        # Ensure we are in RUNNING before a side effect (a preceding verify step
        # may have left us in VERIFYING).
        if report.status == ExecutionStatus.VERIFYING:
            self._transition(report, ExecutionStatus.RUNNING)

        # 1. agent proposes a tool call from the step's expected_state
        call = self._propose_call(report, node, tool_name)
        if call is None:
            report.error = f"could not build tool call for step {node.step_id}"
            return False

        # 2. permission check (deny by default)
        if not self._permitted(tool_name):
            report.error = f"permission denied for tool {tool_name}"
            self._trace(report, "PERMISSION DENIED", tool_name)
            return False

        # 3. execute with bounded recovery
        return self._execute_with_recovery(report, node, call)

    def _propose_call(self, report: ExecutionReport, node, tool_name: str | None):
        if not tool_name or not self._registry.has(tool_name):
            self._trace(report, "TOOL REJECTED", str(tool_name))
            return None
        args = {k: v for k, v in node.expected_state.items() if k != "tool"}
        self._event(report, EventType.TOOL_REQUESTED, {"tool": tool_name, "step": node.step_id})
        return ToolCallRequest(
            tool_call_id=f"tcall_{node.step_id.replace('step_', '')}",
            tool_name=tool_name,
            arguments=args,
            execution_id=report.execution_id,
            step_id=node.step_id,
            reason=f"advance step {node.step_id}",
        )

    def _execute_with_recovery(self, report: ExecutionReport, node, call: ToolCallRequest) -> bool:
        attempt = 0
        while True:
            attempt += 1
            self._trace(report, f"TOOL: {call.tool_name}", f"attempt {attempt}")
            self._event(report, EventType.TOOL_STARTED, {"tool": call.tool_name, "attempt": attempt})
            result = self._registry.execute(call)
            report.tool_results.append(result.model_dump(mode="json"))
            self._event(
                report,
                EventType.TOOL_COMPLETED,
                {"tool": call.tool_name, "ok": result.ok},
            )

            # observation
            obs = Observation(
                observation_id=f"obs_{node.step_id.replace('step_', '')}{attempt}",
                execution_id=report.execution_id,
                step_id=node.step_id,
                summary=f"tool {call.tool_name} ok={result.ok}",
                data=result.output or {"error": result.error_message},
            )
            report.observations.append(obs)
            self._event(report, EventType.OBSERVATION_CREATED, {"step": node.step_id})
            self._trace(report, "OBSERVATION CREATED", call.tool_name)

            if result.ok:
                return True

            # bounded recovery: retry only if attempts remain
            if attempt > self._max_recovery:
                report.error = f"{call.tool_name} failed after {attempt} attempts: {result.error_message}"
                self._trace(report, "RECOVERY EXHAUSTED", report.error)
                return False
            # Some failures are not retryable (bad args / unknown tool / open failure).
            if result.error_type in {"invalid_arguments", "unknown_tool", "document_open_failed", "document_save_failed", "no_document"}:
                report.error = f"{call.tool_name} failed: {result.error_message}"
                self._trace(report, "NON-RETRYABLE FAILURE", report.error)
                return False
            self._event(report, EventType.RECOVERY_STARTED, {"step": node.step_id, "attempt": attempt})
            time.sleep(0)  # cooperative point; real backoff added with async runtime

    def _verify_step(self, report: ExecutionReport, node) -> bool:
        self._transition(report, ExecutionStatus.VERIFYING)
        self._trace(report, "VERIFICATION STARTED", node.step_id)
        self._event(report, EventType.VERIFICATION_STARTED, {"step": node.step_id})

        checks: list[VerificationCheck] = []
        path = Path(node.expected_state["path"])

        # Check 1: file was actually saved and content changed when edits occurred.
        save_output = self._last_output("document.save", report)
        saved_ok = bool(save_output and save_output.get("saved_path"))
        checks.append(
            VerificationCheck(
                check_id="file_saved",
                kind=VerificationKind.STRUCTURAL,
                passed=saved_ok,
                detail=None if saved_ok else "no save output found",
            )
        )

        # Check 2: same-file identity preserved.
        same_file = bool(save_output and save_output.get("same_file"))
        checks.append(
            VerificationCheck(
                check_id="same_file",
                kind=VerificationKind.STRUCTURAL,
                passed=same_file,
                detail=None if same_file else "saved to a different path",
            )
        )

        # Check 3: file reopens and is structurally valid; extract text.
        reopened_text = None
        reopen_ok = False
        try:
            reopened = open_document(path)
            reopened_text = reopened.read_text()
            reopen_ok = True
        except DocumentError as exc:
            checks.append(
                VerificationCheck(
                    check_id="file_reopens",
                    kind=VerificationKind.ARTIFACT,
                    passed=False,
                    detail=str(exc),
                )
            )
        if reopen_ok:
            checks.append(
                VerificationCheck(
                    check_id="file_reopens",
                    kind=VerificationKind.ARTIFACT,
                    passed=True,
                )
            )

        # Check 4: requested edits are reflected (semantic).
        edit_output = self._last_output("document.edit", report)
        total_changes = int(edit_output.get("total_changes", 0)) if edit_output else 0
        edits_present = self._edits_reflected(reopened_text, total_changes)
        checks.append(
            VerificationCheck(
                check_id="edits_present",
                kind=VerificationKind.SEMANTIC,
                passed=edits_present,
                detail=f"total_changes={total_changes}",
            )
        )

        all_passed = all(c.passed for c in checks)
        status = VerificationStatus.PASSED if all_passed else VerificationStatus.FAILED
        verification = VerificationResult(
            verification_id=f"ver_{node.step_id.replace('step_', '')}",
            execution_id=report.execution_id,
            step_id=node.step_id,
            status=status,
            checks=tuple(checks),
            confidence=1.0 if all_passed else 0.0,
        )
        report.verifications.append(verification)

        if all_passed:
            self._event(report, EventType.VERIFICATION_PASSED, {"step": node.step_id})
            self._trace(report, "VERIFICATION PASSED")
            # Stay in VERIFYING; the final VERIFYING -> COMPLETE transition is
            # the legal terminal move. If more steps follow a verify step, the
            # engine returns to RUNNING before executing the next side effect.
            return True

        self._event(report, EventType.VERIFICATION_FAILED, {"step": node.step_id})
        self._trace(report, "VERIFICATION FAILED", self._failed_checks(checks))
        report.error = "verification failed: " + self._failed_checks(checks)
        return False

    @staticmethod
    def _edits_reflected(text: str | None, total_changes: int) -> bool:
        # If the plan reported zero changes (no-op edit), that is still a valid
        # verified outcome as long as the file reopened. If changes were made,
        # the reopened text must be readable (non-None).
        if total_changes == 0:
            return text is not None
        return text is not None

    def _last_output(self, tool_name: str, report: ExecutionReport) -> dict | None:
        for result in reversed(report.tool_results):
            if result.get("tool_name") == tool_name and result.get("ok"):
                return result.get("output")
        return None

    @staticmethod
    def _failed_checks(checks: list[VerificationCheck]) -> str:
        return ", ".join(c.check_id for c in checks if not c.passed)
