"""Planning service.

Runs the planning phase for a queued execution:
  QUEUED -> PLANNING -> (orchestrator) -> persist plan+steps -> plan.created
  -> VALIDATING -> validate -> plan.validated -> (approval detection)
  -> AWAITING_APPROVAL | RUNNING.

The backend stores what the orchestrator returns; it never invents plan logic.

Plan production has two sources behind one seam:
  - mock mode: the deterministic MockOrchestrator (default).
  - integration mode (settings.use_real_intelligence): the real AI/ML runtime,
    which starts a mission and derives the plan from its structure. The Control
    Plane still validates and persists exactly the same way — it does not trust
    the AI/ML plan blindly.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.enums import (
    ActorType,
    EventType,
    PlanValidationStatus,
    StepStatus,
    TaskStatus,
)
from app.intelligence.ai_ml_client import AiMlUnavailable
from app.intelligence.interfaces import MissionRequest
from app.models.execution import Execution
from app.models.plan import TaskPlan, TaskStep
from app.models.task import Task
from app.orchestration import state_machine as sm
from app.repositories import executions as exec_repo
from app.repositories import plans as plans_repo
from app.runtime import get_intelligence_runtime, get_orchestrator
from app.schemas.plan import Plan
from app.schemas.task import TaskRequest
from app.services import audit_service, event_service

log = get_logger("planning_service")


def _target_path_from_task(task: Task) -> str | None:
    """Resolve an optional on-disk target file for a file-shaped mission.

    File-based goals (edit/save a specific document) run via the AI/ML /run
    path; everything else uses /simulate, which still exercises the real
    society orchestration. We only surface a target when the task carries an
    explicit one; otherwise None keeps the mission document-agnostic.
    """
    meta = getattr(task, "client_metadata", None) or {}
    if isinstance(meta, dict):
        tp = meta.get("target_path") or meta.get("target_file")
        if isinstance(tp, str) and tp.strip():
            return tp.strip()
    return None


def _roster_path_from_task(task: Task) -> str | None:
    """Resolve an optional uploaded employee-roster spreadsheet.

    This drives the reassign-work desktop flow. Unlike ``target_path`` it does
    NOT switch the mission to the /run document-edit path — it is handed to the
    AI/ML runtime via context so the (simulate-routed) desktop executor can read
    the spreadsheet and open a work-assignment email.
    """
    meta = getattr(task, "client_metadata", None) or {}
    if isinstance(meta, dict):
        rp = meta.get("roster_path")
        if isinstance(rp, str) and rp.strip():
            return rp.strip()
    return None


_EXTERNAL_ACTION_HINTS = (
    "send", "email", "e-mail", "notify", "deliver", "publish", "post ",
    "share", "message", "report to", "submit",
)


def _needs_approval_gate(task: Task) -> bool:
    """Whether the mission should pause for human approval before acting.

    High-risk external actions (sending an email, publishing, delivering)
    require human approval before they happen. We detect the intent from the
    goal so the mission runs in await-approval mode and parks at the pre-send
    state; the Control Plane then owns the approval decision. Callers may force
    it via client_metadata['require_approval'].
    """
    meta = getattr(task, "client_metadata", None) or {}
    if isinstance(meta, dict) and meta.get("require_approval") is not None:
        return bool(meta.get("require_approval"))
    goal = (task.goal or "").lower()
    return any(hint in goal for hint in _EXTERNAL_ACTION_HINTS)


async def _produce_plan(task: Task, execution: Execution) -> Plan:
    """Obtain a plan for this task from the configured intelligence source.

    In integration mode this starts a real AI/ML mission and derives the plan
    from it (the mission id is carried in plan.risk_summary so the execution
    phase can reconcile against the same mission). In mock mode it uses the
    deterministic orchestrator.
    """
    if settings.use_real_intelligence:
        runtime = get_intelligence_runtime()
        mission_request = MissionRequest(
            task_id=task.id,
            execution_id=execution.id,
            workspace_id=task.workspace_id,
            organization_id=task.organization_id,
            goal=task.goal,
            target_path=_target_path_from_task(task),
            use_model=settings.ai_ml_use_model,
            context={
                "approval_gate": _needs_approval_gate(task),
                **({"roster_path": rp} if (rp := _roster_path_from_task(task)) else {}),
            },
        )
        result = await runtime.create_plan(mission_request)
        plan = result.plan
        # Ensure the plan is bound to this task and carries the external ref.
        plan.task_id = task.id
        summary = dict(plan.risk_summary or {})
        if result.external_ref:
            summary["mission_id"] = result.external_ref
        summary.setdefault("source", "ai-ml")
        plan.risk_summary = summary
        log.info(
            "planning.real_plan_derived",
            task_id=task.id,
            execution_id=execution.id,
            mission_id=result.external_ref,
            steps=len(plan.graph.steps),
        )
        return plan

    orchestrator = get_orchestrator()
    request = TaskRequest(workspace_id=task.workspace_id, goal=task.goal)
    return await orchestrator.create_plan(request)


async def _set_status(
    session: AsyncSession, task: Task, execution: Execution, target: TaskStatus
) -> None:
    """Validate + apply a status transition to both task and execution."""
    current = TaskStatus(execution.status)
    sm.validate_transition(current, target)
    execution.status = target.value
    task.status = target.value


async def _fail_planning(
    session: AsyncSession, task: Task, execution: Execution, reason: str
) -> None:
    """Fail a task during planning (honest terminal state, no fabricated plan)."""
    current = TaskStatus(execution.status)
    if sm.can_transition(current, TaskStatus.FAILED):
        execution.status = TaskStatus.FAILED.value
        task.status = TaskStatus.FAILED.value
    task.failure_reason = reason
    await event_service.emit(
        session,
        type=EventType.EXECUTION_FAILED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        label="Planning failed",
        payload={"reason": reason},
    )


async def run_planning(
    session: AsyncSession, task: Task, execution: Execution
) -> None:
    # Idempotency: only a freshly QUEUED execution should be planned. A
    # redelivered plan job for an already-advanced execution is a safe no-op
    # (worker restart / at-least-once delivery), never a corrupting re-plan.
    if execution.status != TaskStatus.QUEUED.value:
        return

    # QUEUED -> PLANNING
    await _set_status(session, task, execution, TaskStatus.PLANNING)
    await event_service.emit(
        session,
        type=EventType.EXECUTION_STARTED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        actor_type=ActorType.WORKER,
        label="Planning started",
    )

    try:
        plan: Plan = await _produce_plan(task, execution)
    except AiMlUnavailable as exc:
        # The intelligence layer is unreachable: fail the task honestly rather
        # than leaving it stuck in PLANNING. Never fabricate a plan.
        await _fail_planning(
            session, task, execution, f"AI/ML runtime unavailable: {exc}"
        )
        return

    version = await plans_repo.next_plan_version(session, task.id)
    plan_row = TaskPlan(
        task_id=task.id,
        workspace_id=task.workspace_id,
        version=version,
        generated_by=plan.generated_by,
        validation_status=PlanValidationStatus.DRAFT.value,
        risk_summary=plan.risk_summary,
        required_approvals=plan.required_approvals,
        plan_hash=plan.plan_hash,
        graph=plan.graph.model_dump(),
    )
    await plans_repo.add_plan(session, plan_row)

    for spec in plan.graph.steps:
        step = TaskStep(
            id=spec.step_id,
            plan_id=plan_row.id,
            task_id=task.id,
            index=spec.index,
            title=spec.title or spec.objective[:60],
            objective=spec.objective,
            agent_profile=spec.agent_profile,
            dependencies=spec.dependencies,
            allowed_tools=spec.allowed_tools,
            inputs=spec.inputs,
            expected_state=spec.expected_state,
            preconditions=spec.preconditions,
            verification_checks=[c.model_dump() for c in spec.verification_checks],
            risk_class=spec.risk_class.value,
            timeout_seconds=spec.timeout_seconds,
            retry_policy=spec.retry_policy.model_dump(),
            recovery_budget=spec.recovery_budget,
            requires_approval=spec.requires_approval,
            status=StepStatus.WAITING.value,
            current_state="Queued.",
        )
        await plans_repo.add_step(session, step)

    task.current_plan_version = version
    execution.plan_id = plan_row.id
    execution.plan_version = version

    await event_service.emit(
        session,
        type=EventType.PLAN_CREATED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        actor_type=ActorType.ORCHESTRATOR,
        label="Plan generated",
        payload={"version": version, "steps": len(plan.graph.steps)},
    )

    # PLANNING -> VALIDATING
    await _set_status(session, task, execution, TaskStatus.VALIDATING)

    # Deterministic validation: every dependency must reference a known step.
    step_ids = {s.step_id for s in plan.graph.steps}
    valid = all(
        all(dep in step_ids for dep in s.dependencies) for s in plan.graph.steps
    )
    plan_row.validation_status = (
        PlanValidationStatus.VALIDATED.value if valid else PlanValidationStatus.INVALID.value
    )

    if not valid:
        await event_service.emit(
            session,
            type=EventType.PLAN_INVALID,
            execution_id=execution.id,
            task_id=task.id,
            organization_id=task.organization_id,
            workspace_id=task.workspace_id,
            label="Plan invalid",
        )
        await _set_status(session, task, execution, TaskStatus.FAILED)
        task.failure_reason = "Plan validation failed: unresolved dependencies."
        return

    await event_service.emit(
        session,
        type=EventType.PLAN_VALIDATED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        label="Plan validated",
    )
    await audit_service.record(
        session,
        action="plan.created",
        resource_type="plan",
        resource_id=plan_row.id,
        actor="orchestrator",
        actor_type=ActorType.ORCHESTRATOR,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        metadata={"version": version},
    )

    # VALIDATING -> RUNNING (execution begins; step-level approvals are raised
    # by the execution controller when a material action is reached).
    await _set_status(session, task, execution, TaskStatus.RUNNING)
    await exec_repo.compare_and_swap_version(session, execution, execution.version)
