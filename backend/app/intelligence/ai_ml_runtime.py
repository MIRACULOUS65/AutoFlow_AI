"""RealAiMlRuntime — the integration-mode IntelligenceRuntime.

Bridges the Control Plane to the real AI/ML runtime over its HTTP server. The
AI/ML server is mission-shaped and exposes the plan only via events (no plan
endpoint), so this adapter:

  1. create_plan(): creates + runs an AI/ML mission, waits for the plan to
     appear (or the mission to reach a stable state), derives a CP Plan from the
     mission trace, and caches the running mission for run_mission().
  2. run_mission(): waits for the (already-started) mission to reach a terminal
     state, translates its trace into canonical CP events, and maps the verified
     outcome.

Honesty is preserved: verification/outcome come only from the AI/ML mission
report; network faults become controlled failures, never fake success.
"""

from __future__ import annotations

import asyncio
import time

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import new_id
from app.domain.enums import RiskClass, TaskStatus
from app.intelligence.ai_ml_client import AiMlClient, AiMlUnavailable
from app.intelligence.interfaces import (
    IntelligenceEvent,
    MissionOutcome,
    MissionRequest,
    PlanResult,
)
from app.intelligence import mappers
from app.schemas.plan import (
    Plan,
    PlanGraph,
    PlanStepSpec,
    VerificationCheckSpec,
)

log = get_logger("ai_ml_runtime")

_TERMINAL_MISSION = {"complete", "failed", "awaiting_approval"}

# Map an AI/ML event "source"/stage to a plausible CP agent profile so the
# derived plan/graph shows meaningful agents in the desktop.
_SOURCE_TO_AGENT = {
    "supervisor": "agent_planner",
    "planner": "agent_planner",
    "rag": "agent_research",
    "research": "agent_research",
    "document": "agent_document",
    "spreadsheet": "agent_spreadsheet",
    "computer": "agent_automation",
    "browser": "agent_automation",
    "gmail": "agent_communication",
    "verify": "agent_verification",
    "approval": "agent_communication",
}


class RealAiMlRuntime:
    def __init__(self, client: AiMlClient | None = None) -> None:
        self._client = client or AiMlClient()
        # execution_id -> mission_id started during create_plan
        self._missions: dict[str, str] = {}

    async def available(self) -> bool:
        return await self._client.ping()

    def bind_mission(self, execution_id: str, mission_id: str) -> None:
        """Recover the execution -> mission mapping from durable state.

        create_plan() records this in-process, but a worker restart (or a
        separate planning/execution job) loses the in-memory map. The Control
        Plane persists the mission id in plan.risk_summary, so it can re-bind
        the runtime to the same mission before running/observing it.
        """
        if execution_id and mission_id:
            self._missions.setdefault(execution_id, mission_id)

    @staticmethod
    def _approval_gate(request: MissionRequest) -> bool:
        """Whether this mission should pause at the pre-send state for approval.

        The Control Plane is the approval authority. When it wants a human to
        approve the external action (e.g. sending the report) before it
        happens, it runs the mission with await_approval=True: the society does
        everything up to and including verification, then parks at
        `awaiting_approval` WITHOUT performing the external send. The send only
        happens later, in resume_mission(), after the CP records approval.
        """
        return bool(request.context.get("approval_gate"))

    async def create_plan(self, request: MissionRequest) -> PlanResult:
        """Start an AI/ML mission and derive a CP plan from its structure."""
        # An uploaded roster (reassign-work flow) is carried on ctx["roster_path"].
        # It is a *desktop* mission: the AI/ML side reads the spreadsheet and
        # drives Gmail compose, so it runs via /simulate (which auto-routes
        # desktop goals) — NOT /run (which edits a document at target_path).
        # We still hand the path to the mission record so the AI/ML detector can
        # see it, but keep mode="simulation" so behaviour of real file goals is
        # unchanged.
        roster_path = str((request.context or {}).get("roster_path") or "").strip()
        mission_target = request.target_path or (roster_path or None)
        mode = "real" if request.target_path else "simulation"
        rec = await self._client.create_mission(
            request.goal, mode=mode, target_path=mission_target,
            model="auto",
        )
        mission_id = rec["mission_id"]
        self._missions[request.execution_id] = mission_id
        gate = self._approval_gate(request)

        # Kick off execution. Real file-based goals use /run; everything else
        # uses /simulate, which still exercises the real society orchestration
        # (supervisor -> specialists -> tools -> independent verify). When the
        # CP wants an approval gate, simulate with await_approval=True so the
        # mission stops before the external send.
        try:
            if request.target_path:
                await self._client.run_real(
                    mission_id, target_path=request.target_path,
                    use_model=request.use_model or settings.ai_ml_use_model,
                )
            else:
                await self._client.simulate(mission_id, await_approval=gate)
        except AiMlUnavailable:
            raise

        # Give the mission a moment to emit its plan, then derive CP steps.
        steps = await self._derive_steps(mission_id, request.execution_id)
        plan = Plan(
            plan_id=new_id("plan"),
            task_id=request.task_id,
            version=1,
            graph=PlanGraph(steps=steps),
            generated_by="ai-ml",
            required_approvals=sum(1 for s in steps if s.requires_approval),
            risk_summary={"source": "ai-ml", "mission_id": mission_id},
        )
        return PlanResult(plan=plan, external_ref=mission_id, raw=rec)

    async def _derive_steps(
        self, mission_id: str, execution_id: str, *, wait_seconds: float = 8.0
    ) -> list[PlanStepSpec]:
        """Poll the mission trace briefly to derive an ordered set of steps.

        Uses distinct meaningful stages from the event stream. Falls back to a
        single generic step if the mission produced no stage detail yet.
        """
        deadline = time.time() + wait_seconds
        seen: list[tuple[str, str]] = []  # (source, message)
        seen_sources: set[str] = set()
        while time.time() < deadline:
            try:
                trace = await self._client.get_trace(mission_id)
            except AiMlUnavailable:
                break
            for ev in trace:
                src = (ev.get("source") or "stage").lower()
                if src in ("system", "stage", "final"):
                    continue
                if src not in seen_sources:
                    seen_sources.add(src)
                    seen.append((src, ev.get("message") or src))
            rec = await self._safe_get_mission(mission_id)
            if rec and rec.get("status") in _TERMINAL_MISSION and seen:
                break
            if len(seen) >= 5:
                break
            await asyncio.sleep(0.4)

        prefix = new_id("pstep")
        steps: list[PlanStepSpec] = []
        for i, (src, msg) in enumerate(seen, start=1):
            agent = _SOURCE_TO_AGENT.get(src, "agent_planner")
            requires_approval = src in ("approval", "gmail")
            steps.append(
                PlanStepSpec(
                    step_id=f"{prefix}_s{i}",
                    index=i,
                    title=_title_for(src),
                    objective=(msg[:200] if msg else _title_for(src)),
                    agent_profile=agent,
                    dependencies=[f"{prefix}_s{i - 1}"] if i > 1 else [],
                    expected_state=f"{_title_for(src)} completed.",
                    verification_checks=[VerificationCheckSpec(id="mission_verified")]
                    if src == "verify"
                    else [],
                    risk_class=RiskClass.HIGH if requires_approval else RiskClass.LOW,
                    requires_approval=requires_approval,
                )
            )
        if not steps:
            steps.append(
                PlanStepSpec(
                    step_id=f"{prefix}_s1",
                    index=1,
                    title="Execute mission",
                    objective="Execute the goal via the AI/ML mission runtime.",
                    agent_profile="agent_planner",
                    expected_state="Mission verified.",
                    verification_checks=[VerificationCheckSpec(id="mission_verified")],
                )
            )
        return steps

    async def run_mission(self, request: MissionRequest) -> MissionOutcome:
        """Wait for the started mission to finish; translate events + outcome."""
        mission_id = self._missions.get(request.execution_id)
        if mission_id is None:
            # create_plan should have started it; if not, start now. A runtime
            # that is unreachable becomes a controlled failed outcome, never a
            # raised exception or a fake success.
            try:
                plan_result = await self.create_plan(request)
            except AiMlUnavailable as exc:
                return self._failed(f"AI/ML runtime unavailable: {exc}")
            mission_id = plan_result.external_ref or self._missions.get(
                request.execution_id
            )
        if mission_id is None:
            return self._failed("AI/ML mission was not started.")

        rec = await self._wait_terminal(mission_id)
        if rec is None:
            return self._failed("AI/ML mission did not reach a terminal state in time.")
        return await self._outcome_from_record(mission_id, rec)

    async def _outcome_from_record(self, mission_id: str, rec: dict) -> MissionOutcome:
        """Build a MissionOutcome from a terminal mission record + its trace."""
        events = await self._translate_events(mission_id)
        artifacts = await self._safe_get_artifacts(mission_id)
        result = rec.get("result") or {}
        mission_status = (rec.get("status") or "").lower()

        verified = bool(result.get("document_verified") or result.get("complete"))
        outcome_str = str(result.get("outcome") or mission_status)
        reason = result.get("reason")

        if mission_status == "awaiting_approval":
            cp_status = TaskStatus.AWAITING_APPROVAL.value
        elif mission_status == "complete" and verified:
            cp_status = TaskStatus.COMPLETE.value
        elif mission_status == "complete" and not verified:
            # honesty: complete-but-unverified is NOT a success
            cp_status = TaskStatus.FAILED.value
            reason = reason or "Mission completed without verification."
        else:
            cp_status = TaskStatus.FAILED.value

        return MissionOutcome(
            status=cp_status,
            verified=verified,
            outcome=outcome_str,
            reason=reason,
            external_ref=mission_id,
            artifacts=[
                {"name": (a.get("payload") or {}).get("name") or a.get("message") or "artifact"}
                for a in artifacts
            ],
            evidence=list(result.get("verified_tasks") or []),
            events=events,
            raw=rec,
        )

    async def resume_mission(self, request: MissionRequest) -> MissionOutcome:
        """Complete an approval-gated mission AFTER the CP recorded approval.

        The ai-ml server has no resume endpoint for a parked mission, and we do
        not modify it. Instead, now that the external action is authorized, we
        run the completing mission (await_approval=False) which performs the
        send and the independent send verification. The society orchestration is
        deterministic, so this is the same verified outcome the gated mission
        would have reached had it been auto-approved — but the send only happens
        now, after real approval. Honesty is preserved: no send before approval.
        """
        try:
            rec = await self._client.create_mission(
                request.goal, mode="simulation", model="auto",
            )
            mission_id = rec["mission_id"]
            # Rebind the execution to the completing mission.
            self._missions[request.execution_id] = mission_id
            await self._client.simulate(mission_id, await_approval=False)
        except AiMlUnavailable as exc:
            return self._failed(f"AI/ML runtime unavailable on resume: {exc}")

        terminal = await self._wait_terminal(mission_id)
        if terminal is None:
            return self._failed("Resumed mission did not reach a terminal state in time.")
        return await self._outcome_from_record(mission_id, terminal)

    # -- helpers -----------------------------------------------------------

    async def _wait_terminal(self, mission_id: str) -> dict | None:
        deadline = time.time() + settings.ai_ml_timeout_seconds
        while time.time() < deadline:
            rec = await self._safe_get_mission(mission_id)
            if rec and (rec.get("status") or "").lower() in _TERMINAL_MISSION:
                return rec
            await asyncio.sleep(0.5)
        return await self._safe_get_mission(mission_id)

    async def _translate_events(self, mission_id: str) -> list[IntelligenceEvent]:
        try:
            trace = await self._client.get_trace(mission_id)
        except AiMlUnavailable:
            return []
        out: list[IntelligenceEvent] = []
        for ev in trace:
            cp_type = mappers.map_event_type(ev.get("type", ""))
            if cp_type is None:
                continue
            out.append(
                IntelligenceEvent(
                    type=cp_type.value,
                    label=(ev.get("message") or cp_type.value)[:300],
                    status=ev.get("status", "info"),
                    payload={"source": ev.get("source"), **(ev.get("payload") or {})},
                )
            )
        return out

    async def _safe_get_mission(self, mission_id: str) -> dict | None:
        try:
            return await self._client.get_mission(mission_id)
        except AiMlUnavailable:
            return None

    async def _safe_get_artifacts(self, mission_id: str) -> list[dict]:
        try:
            return await self._client.get_artifacts(mission_id)
        except AiMlUnavailable:
            return []

    @staticmethod
    def _failed(reason: str) -> MissionOutcome:
        return MissionOutcome(
            status=TaskStatus.FAILED.value,
            verified=False,
            outcome="failed",
            reason=reason,
        )


def _title_for(source: str) -> str:
    return {
        "supervisor": "Plan mission",
        "planner": "Create plan",
        "rag": "Retrieve evidence",
        "research": "Research",
        "document": "Edit document",
        "spreadsheet": "Build spreadsheet",
        "computer": "Automate desktop",
        "browser": "Automate browser",
        "gmail": "Prepare email",
        "verify": "Verify outcome",
        "approval": "Request approval",
        "cleanup": "Clean up",
    }.get(source, source.title())
