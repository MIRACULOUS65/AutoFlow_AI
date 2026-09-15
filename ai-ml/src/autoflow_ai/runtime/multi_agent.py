"""Multi-agent runtime: schedule a validated task graph to a verified outcome.

Composes Phase 1-5:
* task graph + node state machine (planning package)
* specialist agents propose structured actions (agents package)
* ToolRegistry executes approved tools (Phase 4/vertical slice authority)
* verification closes each material step
* bounded replanning on failure

Concurrency: independent READY nodes run in a bounded thread pool. Tool
execution against the shared registry is serialized per-tool via a lock to
avoid conflicting mutations (document session is single-target here).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import timezone

from ..agents.models import AgentContext, AgentResult, AgentStatus
from ..agents.registry import AgentRegistry
from ..planning.models import NodeStatus, PlanNode, RuntimeGraph
from ..schemas.common import utcnow
from ..schemas.tools import ToolCallRequest
from .registry import ToolRegistry


@dataclass
class MAEvent:
    type: str
    task_id: str | None = None
    detail: str = ""


@dataclass
class MultiAgentReport:
    execution_id: str
    graph: RuntimeGraph
    events: list[MAEvent] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    replans: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.graph.is_complete() and not self.graph.has_failure()

    def trace(self) -> list[dict]:
        return [{"type": e.type, "task_id": e.task_id, "detail": e.detail} for e in self.events]


class MultiAgentRuntime:
    def __init__(
        self,
        *,
        agents: AgentRegistry,
        tools: ToolRegistry,
        permissions: frozenset[str],
        verifier=None,
        max_concurrency: int = 4,
        max_replans: int = 2,
        replanner=None,
    ) -> None:
        self._agents = agents
        self._tools = tools
        self._permissions = permissions
        self._verifier = verifier
        self._max_concurrency = max(1, max_concurrency)
        self._max_replans = max_replans
        self._replanner = replanner
        self._tool_lock = threading.Lock()

    # -- events --------------------------------------------------------------

    def _emit(self, report: MultiAgentReport, etype: str, task_id: str | None = None, detail: str = "") -> None:
        report.events.append(MAEvent(type=etype, task_id=task_id, detail=detail))

    # -- main loop -----------------------------------------------------------

    def run(self, graph: RuntimeGraph) -> MultiAgentReport:
        report = MultiAgentReport(execution_id=graph.execution_id, graph=graph)
        self._emit(report, "PLAN_VALIDATED", detail=f"{len(graph.nodes)} nodes")

        while True:
            # A failure is handled before completion so bounded replanning can
            # recover (a FAILED node is otherwise terminal and would end the run).
            if graph.has_failure():
                if self._attempt_replan(report):
                    continue
                report.error = "execution failed and replanning exhausted/unavailable"
                self._emit(report, "EXECUTION_FAILED", detail=report.error)
                self._cancel_remaining(graph)
                return report

            if graph.is_complete():
                break

            ready = graph.ready_nodes()
            if not ready:
                report.error = "deadlock: no ready nodes and graph not complete"
                self._emit(report, "EXECUTION_FAILED", detail=report.error)
                self._cancel_remaining(graph)
                return report

            self._run_ready_batch(report, ready)

        self._emit(report, "GRAPH_COMPLETED", detail=f"succeeded={list(graph.succeeded_ids())}")
        return report

    def _run_ready_batch(self, report: MultiAgentReport, ready: list[PlanNode]) -> None:
        # mark READY -> RUNNING (guard transitions)
        runnable: list[PlanNode] = []
        for node in ready:
            if node.status in (NodeStatus.PENDING, NodeStatus.WAITING):
                node.status = NodeStatus.READY
            if node.can_transition_to(NodeStatus.RUNNING):
                node.status = NodeStatus.RUNNING
                node.started_at = utcnow().replace(tzinfo=timezone.utc)
                self._emit(report, "TASK_READY", node.task_id)
                runnable.append(node)

        if len(runnable) == 1:
            self._execute_node(report, runnable[0])
            return

        # bounded concurrency for independent ready nodes
        with ThreadPoolExecutor(max_workers=min(self._max_concurrency, len(runnable))) as pool:
            futures = {pool.submit(self._execute_node, report, n): n for n in runnable}
            for fut in futures:
                fut.result()

    def _execute_node(self, report: MultiAgentReport, node: PlanNode) -> None:
        agent = self._agents.get(node.agent_type)
        self._emit(report, "AGENT_ASSIGNED", node.task_id, str(node.agent_type))
        if agent is None:
            self._fail(report, node, f"no agent for {node.agent_type}")
            return

        context = self._build_agent_context(report, node)
        self._emit(report, "AGENT_STARTED", node.task_id)
        try:
            result = agent.propose(context)
        except Exception as exc:  # noqa: BLE001
            self._fail(report, node, f"agent error: {exc!r}")
            return

        self._handle_result(report, node, result)

    def _handle_result(self, report: MultiAgentReport, node: PlanNode, result: AgentResult) -> None:
        if result.status == AgentStatus.UNSUPPORTED:
            self._fail(report, node, "; ".join(result.warnings) or "unsupported capability")
            return
        if result.status == AgentStatus.FAILED:
            self._fail(report, node, result.reasoning_summary or "agent failed")
            return

        if result.proposed_action is None:
            # no side effect (e.g. research synthesis) -> succeed with output
            self._succeed(report, node, result.output)
            return

        self._emit(report, "ACTION_PROPOSED", node.task_id, result.proposed_action.tool_name)
        tool_name = result.proposed_action.tool_name

        # verification tool is handled by the verifier hook, not a side-effect tool
        if tool_name.endswith(".verify"):
            ok = self._verify(report, node, result)
            if ok:
                self._succeed(report, node, {"verified": True})
            else:
                self._fail(report, node, "verification failed")
            return

        # validate + policy + permission + execute (authority chain)
        if not self._tools.has(tool_name):
            self._emit(report, "ACTION_REJECTED", node.task_id, f"unknown tool {tool_name}")
            self._fail(report, node, f"unknown/unregistered tool: {tool_name}")
            return
        definition = self._tools.definition(tool_name)
        if definition.permission_scope not in self._permissions:
            self._emit(report, "ACTION_REJECTED", node.task_id, "permission denied")
            self._fail(report, node, f"permission denied for {tool_name}")
            return
        if definition.requires_approval:
            self._emit(report, "APPROVAL_REQUIRED", node.task_id, tool_name)
            self._fail(report, node, f"approval required for {tool_name} (not granted in headless run)")
            return

        call = ToolCallRequest(
            tool_call_id=self._call_id(node),
            tool_name=tool_name,
            arguments=result.proposed_action.tool_args,
            execution_id=report.execution_id,
            step_id=self._step_id(node),
            reason=result.reasoning_summary[:200] or f"advance {node.task_id}",
        )
        with self._tool_lock:
            tool_result = self._tools.execute(call)
        report.tool_results.append(tool_result.model_dump(mode="json"))
        self._emit(report, "TOOL_EXECUTED", node.task_id, f"{tool_name} ok={tool_result.ok}")
        self._emit(report, "OBSERVATION_RECORDED", node.task_id)

        if not tool_result.ok:
            self._fail(report, node, f"{tool_name} failed: {tool_result.error_message}")
            return
        self._succeed(report, node, tool_result.output or {})

    # -- verification --------------------------------------------------------

    def _verify(self, report: MultiAgentReport, node: PlanNode, result: AgentResult) -> bool:
        self._emit(report, "TASK_VERIFYING", node.task_id)
        if self._verifier is None:
            # structural fallback: ensure prior save produced output
            saved = any(
                r.get("tool_name") == "document.save" and r.get("ok") for r in report.tool_results
            )
            passed = saved or not any(r.get("tool_name") == "document.save" for r in report.tool_results)
        else:
            passed = self._verifier(report, node, result)
        self._emit(report, "TASK_VERIFIED" if passed else "TASK_FAILED", node.task_id)
        return passed

    # -- state helpers -------------------------------------------------------

    def _succeed(self, report: MultiAgentReport, node: PlanNode, output: dict) -> None:
        node.status = NodeStatus.SUCCEEDED
        node.output = output
        node.completed_at = utcnow().replace(tzinfo=timezone.utc)
        self._emit(report, "TASK_SUCCEEDED", node.task_id)

    def _fail(self, report: MultiAgentReport, node: PlanNode, reason: str) -> None:
        node.status = NodeStatus.FAILED
        node.failure_reason = reason
        node.completed_at = utcnow().replace(tzinfo=timezone.utc)
        self._emit(report, "TASK_FAILED", node.task_id, reason)
        # block dependents
        for dep in report.graph.dependents_of(node.task_id):
            if dep.status in (NodeStatus.PENDING, NodeStatus.READY, NodeStatus.WAITING):
                dep.status = NodeStatus.BLOCKED

    def _cancel_remaining(self, graph: RuntimeGraph) -> None:
        for n in graph.nodes:
            if n.status in (NodeStatus.PENDING, NodeStatus.READY, NodeStatus.WAITING, NodeStatus.BLOCKED):
                if n.can_transition_to(NodeStatus.CANCELLED):
                    n.status = NodeStatus.CANCELLED

    def _attempt_replan(self, report: MultiAgentReport) -> bool:
        if self._replanner is None or report.replans >= self._max_replans:
            return False
        failed = [n for n in report.graph.nodes if n.status == NodeStatus.FAILED]
        if not failed:
            return False
        report.replans += 1
        self._emit(report, "REPLAN_REQUESTED", detail=f"attempt {report.replans}")
        changed = self._replanner(report.graph, failed)
        self._emit(report, "REPLAN_COMPLETED", detail=f"changed={changed}")
        return bool(changed)

    def _build_agent_context(self, report: MultiAgentReport, node: PlanNode) -> AgentContext:
        prior = {
            n.task_id: (n.output or {})
            for n in report.graph.nodes
            if n.status == NodeStatus.SUCCEEDED and n.output
        }
        return AgentContext(
            execution_id=report.execution_id,
            task_id=node.task_id,
            tenant_id="org_local",
            workspace_id="ws_local",
            actor="user_local",
            objective=node.objective,
            parameters=node.parameters,
            available_tools=frozenset(self._tools.names()),
            permissions=self._permissions,
            prior_outputs=prior,
            context_summary=node.parameters.get("context_summary", ""),
        )

    @staticmethod
    def _sanitize(task_id: str) -> str:
        # produce a valid id token (alphanumeric, no leading/trailing underscore)
        import re

        base = re.sub(r"[^A-Za-z0-9]", "", task_id) or "n"
        return base[:60]

    def _step_id(self, node: PlanNode) -> str:
        return f"step_{self._sanitize(node.task_id)}"

    def _call_id(self, node: PlanNode) -> str:
        return f"tcall_{self._sanitize(node.task_id)}"
