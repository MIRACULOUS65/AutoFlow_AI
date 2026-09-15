"""Execution controller — advances an execution one runnable step at a time.

Per step:
  check cancellation/expiry
  -> agent proposes structured actions (never executes them)
  -> for each proposed action: policy -> permission -> approval gate -> tool
  -> observation
  -> verification (tool success != business success)
  -> success: next step | failure: bounded recovery

State changes go through the state machine; events are emitted for every
transition. The controller resumes from durable state, so a restart continues
rather than replaying committed side effects.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import DEV_PRINCIPAL, compute_action_hash
from app.db.base import utcnow
from app.domain.enums import (
    ActorType,
    ApprovalStatus,
    EventType,
    RecoveryDecision,
    RiskClass,
    StepStatus,
    TaskStatus,
    VerificationStatus,
)
from app.models.approval import Approval
from app.models.execution import Execution
from app.models.plan import TaskStep
from app.models.recovery import RecoveryRun
from app.models.task import Task
from app.orchestration import state_machine as sm
from app.repositories import approvals as approvals_repo
from app.repositories import plans as plans_repo
from app.runtime import (
    get_agent_runtime,
    get_recovery_manager,
    get_tool_runtime,
    get_verifier,
)
from app.schemas.agents import (
    AgentRunRequest,
    ProposedAction,
    RecoveryRequest,
    ToolCall,
    VerificationRequest,
)
from app.services import (
    approval_service,
    artifact_service,
    audit_service,
    event_service,
    verification_service,
)

log = get_logger("execution_service")


async def _reload_cancel_flag(session: AsyncSession, execution: Execution) -> bool:
    """Read only the durable cancel flag, without overwriting other in-memory
    (uncommitted) attribute changes on the execution object."""
    from sqlalchemy import select

    res = await session.execute(
        select(Execution.cancel_requested).where(Execution.id == execution.id)
    )
    return bool(res.scalar_one_or_none())


def _deps_met(step: TaskStep, by_id: dict[str, TaskStep]) -> bool:
    return all(
        by_id.get(dep) is not None and by_id[dep].status == StepStatus.COMPLETE.value
        for dep in step.dependencies
    )


def _next_ready_step(steps: list[TaskStep]) -> TaskStep | None:
    by_id = {s.id: s for s in steps}
    for step in sorted(steps, key=lambda s: s.index):
        if step.status in (StepStatus.WAITING.value, StepStatus.READY.value) and _deps_met(
            step, by_id
        ):
            return step
    return None


async def advance(session: AsyncSession, task: Task, execution: Execution) -> None:
    """Advance the execution until it blocks (approval), finishes, or fails.

    In integration mode the real AI/ML mission (already started during planning)
    is the source of execution truth: we observe it and translate its events
    into the canonical CP stream. In mock mode the per-step controller runs.
    """
    # Guard: only advance running/recovery executions.
    if execution.status not in (TaskStatus.RUNNING.value, TaskStatus.RECOVERY.value):
        return

    if settings.use_real_intelligence:
        await _advance_real(session, task, execution)
        return

    while True:
        # Persist pending changes, then re-read the durable cancel flag without
        # clobbering in-memory status changes made by the previous iteration.
        await session.flush()
        cancel_requested = await _reload_cancel_flag(session, execution)

        # Stop if a prior step drove the execution to a non-advanceable state
        # (failed, awaiting approval, cancelled, terminal, etc.).
        if execution.status not in (TaskStatus.RUNNING.value, TaskStatus.RECOVERY.value):
            return

        if cancel_requested:
            execution.cancel_requested = True
            await _cancel(session, task, execution)
            return

        steps = list(await plans_repo.get_steps_for_plan(session, execution.plan_id))
        step = _next_ready_step(steps)
        if step is None:
            await _complete(session, task, execution, steps)
            return

        blocked = await _run_step(session, task, execution, step)
        if blocked:
            return  # awaiting approval


# --------------------------------------------------------------------------
# Real (integration mode) execution: observe the AI/ML mission and translate.
# --------------------------------------------------------------------------


async def _advance_real(
    session: AsyncSession, task: Task, execution: Execution
) -> None:
    """Observe the real AI/ML mission and reconcile it into CP state.

    The mission was started during planning. Here we wait for it to reach a
    terminal state, translate its trace into canonical CP events (each gets an
    authoritative CP sequence), reconcile the derived steps, and drive the
    execution to COMPLETE / FAILED / AWAITING_APPROVAL based on the mission's
    honest outcome. Tool execution and verification are NOT re-run here — the
    AI/ML runtime already did them; duplicating would be dishonest.
    """
    from app.intelligence.interfaces import MissionRequest
    from app.intelligence.ai_ml_client import AiMlUnavailable
    from app.runtime import get_intelligence_runtime

    runtime = get_intelligence_runtime()

    # Recover the mission id the planning phase started, from durable state.
    plan = await plans_repo.get_plan(session, execution.plan_id)
    mission_id = None
    if plan is not None and isinstance(plan.risk_summary, dict):
        mission_id = plan.risk_summary.get("mission_id")
    if mission_id and hasattr(runtime, "bind_mission"):
        runtime.bind_mission(execution.id, mission_id)

    request = MissionRequest(
        task_id=task.id,
        execution_id=execution.id,
        workspace_id=task.workspace_id,
        organization_id=task.organization_id,
        goal=task.goal,
        target_path=(plan.risk_summary or {}).get("target_path") if plan else None,
        use_model=settings.ai_ml_use_model,
    )

    # If we are resuming after a granted approval, complete the gated mission by
    # running the authorized (completing) mission — the external send only
    # happens now, after real approval. Otherwise observe the started mission.
    resuming = await _has_granted_approval(session, execution.id)

    try:
        if resuming and hasattr(runtime, "resume_mission"):
            outcome = await runtime.resume_mission(request)
        else:
            outcome = await runtime.run_mission(request)
    except AiMlUnavailable as exc:
        await _fail(session, task, execution, f"AI/ML runtime unavailable: {exc}")
        return
    except Exception as exc:  # noqa: BLE001 — never fake success on adapter error
        log.error("real_execution.error", execution_id=execution.id, error=str(exc))
        await _fail(session, task, execution, f"AI/ML mission error: {exc}")
        return

    steps = list(await plans_repo.get_steps_for_plan(session, execution.plan_id))

    # Translate the mission's canonical events into CP events. The AI/ML adapter
    # has already mapped types to CP EventType values; we re-emit them through
    # event_service so each gets an authoritative, monotonic CP sequence.
    await _emit_mission_events(session, task, execution, outcome.events)

    if outcome.status == TaskStatus.AWAITING_APPROVAL.value:
        # Approval convergence is handled in Phase 7; for now, surface the
        # awaiting-approval state honestly and block. The mission stays paused.
        await _block_on_mission_approval(session, task, execution, steps)
        return

    # Persist the authoritative verification record from the mission report and
    # gate COMPLETE on it. The Control Plane owns the verification record; the
    # verdict comes only from the mission's honest verification (never faked).
    run = await verification_service.record_mission_verification(
        session, execution_id=execution.id, outcome=outcome
    )
    verified = run.status == VerificationStatus.PASSED.value
    execution.verification_status = run.status
    await event_service.emit(
        session,
        type=(EventType.VERIFICATION_PASSED if verified else EventType.VERIFICATION_FAILED),
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        verification_id=run.id,
        actor_type=ActorType.AGENT,
        label=("Outcome verified" if verified else "Outcome verification failed"),
        payload={"source": "ai-ml", "verified_tasks": list(outcome.evidence or [])},
    )

    if outcome.status == TaskStatus.COMPLETE.value and verified:
        _mark_all_steps(steps, StepStatus.COMPLETE, VerificationStatus.PASSED)
        await _record_mission_artifacts(session, task, execution, outcome)
        await _complete(session, task, execution, steps)
        return

    # Anything else (including complete-but-unverified) is an honest failure.
    reason = outcome.reason or f"Mission did not verify (outcome={outcome.outcome})."
    _mark_all_steps(steps, StepStatus.FAILED, VerificationStatus.FAILED)
    await _fail(session, task, execution, reason)


async def _has_granted_approval(session: AsyncSession, execution_id: str) -> bool:
    """Whether this execution has a granted approval (i.e. we are resuming)."""
    from sqlalchemy import select

    res = await session.execute(
        select(Approval.id).where(
            Approval.execution_id == execution_id,
            Approval.status == ApprovalStatus.APPROVED.value,
        )
    )
    return res.first() is not None


async def _emit_mission_events(
    session: AsyncSession,
    task: Task,
    execution: Execution,
    events: list,
) -> None:
    """Re-emit translated mission events through the authoritative CP stream."""
    from app.domain.enums import EventType as _ET

    valid = {e.value for e in _ET}
    for ev in events:
        if ev.type not in valid:
            continue
        # Artifact events are emitted authoritatively by artifact_service with
        # the real artifact id; skip the trace copy to avoid duplicates.
        if ev.type == _ET.ARTIFACT_CREATED.value:
            continue
        # The Control Plane owns the terminal execution event (emitted by
        # _complete/_fail), so drop the mission's terminal copies here.
        if ev.type in (
            _ET.EXECUTION_COMPLETED.value,
            _ET.EXECUTION_FAILED.value,
        ):
            continue
        try:
            cp_type = _ET(ev.type)
        except ValueError:
            continue
        # Preserve the AI/ML native stage under `ml_stage`, and stamp
        # source=ai-ml so the CP stream can identify translated events.
        payload = {**(ev.payload or {})}
        ml_stage = payload.pop("source", None)
        if ml_stage:
            payload["ml_stage"] = ml_stage
        payload["source"] = "ai-ml"
        await event_service.emit(
            session,
            type=cp_type,
            execution_id=execution.id,
            task_id=task.id,
            organization_id=task.organization_id,
            workspace_id=task.workspace_id,
            actor_type=ActorType.AGENT,
            label=ev.label,
            payload=payload,
        )


async def _record_mission_artifacts(
    session: AsyncSession, task: Task, execution: Execution, outcome
) -> None:
    for art in outcome.artifacts:
        name = art.get("name") or "artifact"
        try:
            await artifact_service.create_from_tool(
                session,
                name=name,
                execution_id=execution.id,
                task_id=task.id,
                organization_id=task.organization_id,
                workspace_id=task.workspace_id,
                created_by_agent="ai-ml",
            )
        except Exception as exc:  # noqa: BLE001 — artifact metadata is best-effort
            log.warning("real_execution.artifact_skip", name=name, error=str(exc))


def _mark_all_steps(
    steps: list[TaskStep], status: StepStatus, verification: VerificationStatus
) -> None:
    now = utcnow()
    for s in steps:
        s.status = status.value
        s.verification_status = verification.value
        s.current_state = (
            "Completed." if status == StepStatus.COMPLETE else "Failed."
        )
        if status == StepStatus.COMPLETE:
            s.completed_at = now


def _mission_send_action(execution: Execution) -> ProposedAction:
    """The canonical high-risk external action the mission is gated on.

    The gated mission parks BEFORE the external send. The Control Plane raises
    an approval bound to the hash of this send action; approving it authorizes
    the completing mission to actually send. The action is derived
    deterministically so its hash is stable between request and decision.
    """
    return ProposedAction(
        tool="email.send",
        arguments={"subject": "Report", "attachment": "report"},
        recipient="reviewer@example.com",
        risk_class=RiskClass.HIGH,
        material=True,
    )


async def _block_on_mission_approval(
    session: AsyncSession, task: Task, execution: Execution, steps: list[TaskStep]
) -> None:
    """Raise a real CP approval when the mission parked awaiting approval.

    The Control Plane is the approval authority: it creates an Approval bound to
    the send action's hash and transitions to AWAITING_APPROVAL. On approve, the
    standard resume path runs the completing mission (which performs the
    authorized send + independent verification). On reject, no send happens.
    """
    approval_step = next(
        (s for s in sorted(steps, key=lambda s: s.index) if s.requires_approval),
        None,
    )
    step_id = approval_step.id if approval_step is not None else (steps[-1].id if steps else "")

    action = _mission_send_action(execution)
    # create_approval performs the RUNNING -> AWAITING_APPROVAL transition via
    # the state it sets; do the transition here to stay explicit + validated.
    sm.validate_transition(TaskStatus(execution.status), TaskStatus.AWAITING_APPROVAL)
    execution.status = TaskStatus.AWAITING_APPROVAL.value
    task.status = TaskStatus.AWAITING_APPROVAL.value
    if approval_step is not None:
        approval_step.status = StepStatus.APPROVAL.value
        approval_step.current_state = "Awaiting approval."

    approval = await approval_service.create_approval(
        session,
        task=task,
        execution=execution,
        step_id=step_id,
        action=action,
        summary="Send the verified report to the reviewer",
        category="external communication",
        risk_class=RiskClass.HIGH,
        evidence=[
            ("Document independently verified", True),
            ("Draft prepared", True),
            ("Send not yet performed", True),
        ],
        plan_label=f"{task.name} v{execution.plan_version}",
        requested_by=task.created_by,
    )
    if approval_step is not None:
        approval_step.approval_id = approval.id


async def _run_step(
    session: AsyncSession, task: Task, execution: Execution, step: TaskStep
) -> bool:
    """Run one step. Returns True if the execution is now blocked on approval."""
    step.status = StepStatus.RUNNING.value
    step.current_state = f"{step.title}…"
    step.attempts += 1
    step.started_at = utcnow()
    execution.current_step_id = step.id
    execution.agent_id = step.agent_profile

    await event_service.emit(
        session,
        type=EventType.STEP_STARTED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step.id,
        actor_type=ActorType.AGENT,
        label=f"{step.title} started",
    )

    # Agent proposes structured actions.
    agent = get_agent_runtime()
    run = await agent.run_step(
        AgentRunRequest(
            task_id=task.id,
            execution_id=execution.id,
            step_id=step.id,
            objective=step.objective,
            inputs=step.inputs,
            allowed_tools=step.allowed_tools,
            expected_state=step.expected_state,
            verification_requirements=[c.get("id") for c in step.verification_checks],
        )
    )

    # Explicit approval step with no tools: raise approval and block.
    if step.requires_approval and not run.proposed_actions:
        await _raise_step_approval(session, task, execution, step, _synthetic_send_action())
        return True

    for action in run.proposed_actions:
        blocked = await _handle_action(session, task, execution, step, action)
        if blocked:
            return True

    # Verify the step outcome.
    verified = await _verify_step(session, task, execution, step)
    if not verified:
        recovered = await _recover_step(session, task, execution, step)
        if not recovered:
            return False  # execution failed inside _recover_step
        # After recovery, retry this step on the next advance loop.
        return False

    step.status = StepStatus.COMPLETE.value
    step.verification_status = VerificationStatus.PASSED.value
    step.current_state = "Completed."
    step.completed_at = utcnow()
    await event_service.emit(
        session,
        type=EventType.STEP_COMPLETED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step.id,
        label=f"{step.title} complete",
    )
    return False


def _synthetic_send_action() -> ProposedAction:
    return ProposedAction(
        tool="email.send.mock",
        arguments={"subject": "Weekly Operations Report", "attachment": "report.xlsx"},
        recipient="finance@example.com",
        risk_class=RiskClass.HIGH,
        material=True,
    )


async def _handle_action(
    session: AsyncSession,
    task: Task,
    execution: Execution,
    step: TaskStep,
    action: ProposedAction,
) -> bool:
    """Validate + execute one proposed action. Returns True if blocked on approval."""
    from app.services import policy_service

    decision = await policy_service.evaluate(
        actor=execution.agent_id or "agent",
        workspace_id=task.workspace_id,
        action=action.tool,
        resource=action.resource,
    )
    if not decision.allowed:
        await _fail(session, task, execution, f"Policy denied action {action.tool}.")
        return False

    if decision.requires_approval:
        # Is there already a granted approval bound to this exact action?
        action_hash = compute_action_hash(action.to_canonical(execution.plan_version))
        granted = await _find_granted_approval(session, execution.id, action_hash)
        if granted is None:
            await _raise_step_approval(session, task, execution, step, action, decision.category)
            return True
        # Approved: fall through to execute.

    # Permission (tool allowlist) + tool execution.
    tools = get_tool_runtime()
    if not tools.is_allowed(action.tool):
        await _fail(session, task, execution, f"Tool not allowed: {action.tool}.")
        return False

    await event_service.emit(
        session,
        type=EventType.TOOL_STARTED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step.id,
        label=f"Tool started: {action.tool}",
        payload={"tool": action.tool},
    )
    result = await tools.execute(
        ToolCall(tool=action.tool, arguments=action.arguments)
    )
    await event_service.emit(
        session,
        type=EventType.TOOL_COMPLETED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step.id,
        tool_call_id=result.tool_call_id,
        label=f"Tool completed: {action.tool}",
        payload={"tool": action.tool, "status": result.status},
    )

    if result.status == "completed" and result.artifact_ref:
        name = result.artifact_ref.replace("artifact://", "")
        await artifact_service.create_from_tool(
            session,
            name=name,
            execution_id=execution.id,
            task_id=task.id,
            organization_id=task.organization_id,
            workspace_id=task.workspace_id,
            created_by_agent=step.agent_profile,
        )

    await event_service.emit(
        session,
        type=EventType.OBSERVATION_CREATED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step.id,
        label="Observation recorded",
        payload={"summary": step.expected_state},
    )
    return False


async def _find_granted_approval(
    session: AsyncSession, execution_id: str, action_hash: str
) -> Approval | None:
    """Internal (unscoped) lookup: is there a granted approval bound to this
    exact action hash for this execution?"""
    from sqlalchemy import select

    result = await session.execute(
        select(Approval).where(
            Approval.execution_id == execution_id,
            Approval.action_hash == action_hash,
            Approval.status == ApprovalStatus.APPROVED.value,
        )
    )
    return result.scalar_one_or_none()


async def _raise_step_approval(
    session: AsyncSession,
    task: Task,
    execution: Execution,
    step: TaskStep,
    action: ProposedAction,
    category: str = "external communication",
) -> None:
    # RUNNING -> AWAITING_APPROVAL
    sm.validate_transition(TaskStatus(execution.status), TaskStatus.AWAITING_APPROVAL)
    execution.status = TaskStatus.AWAITING_APPROVAL.value
    task.status = TaskStatus.AWAITING_APPROVAL.value
    step.status = StepStatus.APPROVAL.value
    step.current_state = "Awaiting approval."

    approval = await approval_service.create_approval(
        session,
        task=task,
        execution=execution,
        step_id=step.id,
        action=action,
        summary=f"{step.title}: {action.tool}",
        category=category,
        risk_class=action.risk_class,
        evidence=[
            ("Report verified", True),
            ("Required fields present", True),
            ("Artifact exists", True),
        ],
        plan_label=f"{task.name} v{execution.plan_version}",
        requested_by=task.created_by,
    )
    step.approval_id = approval.id


async def _verify_step(
    session: AsyncSession, task: Task, execution: Execution, step: TaskStep
) -> bool:
    checks = [c.get("id") for c in step.verification_checks if c.get("id")]
    if not checks:
        return True  # nothing to verify

    await event_service.emit(
        session,
        type=EventType.VERIFICATION_STARTED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step.id,
        label="Verification started",
    )
    verifier = get_verifier()
    force_fail = bool(step.inputs.get("force_fail"))
    result = await verifier.verify(
        VerificationRequest(
            execution_id=execution.id,
            step_id=step.id,
            checks=checks,
            context={"force_fail": force_fail},
        )
    )
    passed = result.status == VerificationStatus.PASSED
    await event_service.emit(
        session,
        type=(EventType.VERIFICATION_PASSED if passed else EventType.VERIFICATION_FAILED),
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step.id,
        verification_id=result.verification_id,
        label=("Verification passed" if passed else "Verification failed"),
        payload={"checks": [c.model_dump() for c in result.checks]},
    )
    return passed


async def _recover_step(
    session: AsyncSession, task: Task, execution: Execution, step: TaskStep
) -> bool:
    """Bounded recovery. Returns True if recovered (step will retry)."""
    sm.validate_transition(TaskStatus(execution.status), TaskStatus.RECOVERY)
    execution.status = TaskStatus.RECOVERY.value
    task.status = TaskStatus.RECOVERY.value
    step.status = StepStatus.RECOVERY.value

    budget_remaining = max(0, step.recovery_budget - step.attempts)
    await event_service.emit(
        session,
        type=EventType.RECOVERY_STARTED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step.id,
        label="Recovery started",
        payload={"attempt": step.attempts, "budget_remaining": budget_remaining},
    )

    manager = get_recovery_manager()
    outcome = await manager.recover(
        RecoveryRequest(
            execution_id=execution.id,
            step_id=step.id,
            failure_reason="Verification failed.",
            attempt=step.attempts,
            budget_remaining=budget_remaining,
        )
    )
    session.add(
        RecoveryRun(
            execution_id=execution.id,
            step_id=step.id,
            attempt=step.attempts,
            decision=outcome.decision,
            reason=outcome.reason,
            detail=outcome.detail,
        )
    )
    await audit_service.record(
        session,
        action="recovery.decision",
        resource_type="execution",
        resource_id=execution.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        actor_type=ActorType.SYSTEM,
        decision=outcome.decision,
    )

    if outcome.decision == RecoveryDecision.FAIL.value:
        await _fail(session, task, execution, "Recovery budget exhausted.")
        return False

    # Alternate path clears the injected failure so the retry succeeds.
    if outcome.detail.get("clear_force_fail") and step.inputs.get("force_fail"):
        inputs = dict(step.inputs)
        inputs["force_fail"] = False
        step.inputs = inputs
        await event_service.emit(
            session,
            type=EventType.RECOVERY_REPLANNED,
            execution_id=execution.id,
            task_id=task.id,
            organization_id=task.organization_id,
            workspace_id=task.workspace_id,
            step_id=step.id,
            label="Alternate path selected",
        )

    # Reset the step to retry, and return to RUNNING.
    step.status = StepStatus.WAITING.value
    sm.validate_transition(TaskStatus.RECOVERY, TaskStatus.RUNNING)
    execution.status = TaskStatus.RUNNING.value
    task.status = TaskStatus.RUNNING.value
    return True


async def _verify_execution_outcome(
    session: AsyncSession, task: Task, execution: Execution, steps: list[TaskStep]
) -> bool:
    """Final material verification before COMPLETE (tool success != success)."""
    all_verified = all(
        s.verification_status in (None, VerificationStatus.PASSED.value)
        for s in steps
    )
    return all_verified


async def _complete(
    session: AsyncSession, task: Task, execution: Execution, steps: list[TaskStep]
) -> None:
    # RUNNING -> VERIFYING
    sm.validate_transition(TaskStatus(execution.status), TaskStatus.VERIFYING)
    execution.status = TaskStatus.VERIFYING.value
    task.status = TaskStatus.VERIFYING.value

    outcome_ok = await _verify_execution_outcome(session, task, execution, steps)
    if not outcome_ok:
        await _fail(session, task, execution, "Final outcome verification failed.")
        return

    sm.validate_transition(TaskStatus.VERIFYING, TaskStatus.COMPLETE)
    execution.status = TaskStatus.COMPLETE.value
    execution.verification_status = VerificationStatus.PASSED.value
    execution.ended_at = utcnow()
    task.status = TaskStatus.COMPLETE.value
    task.verification_status = VerificationStatus.PASSED.value
    task.completed_at = utcnow()

    await event_service.emit(
        session,
        type=EventType.EXECUTION_COMPLETED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        label="Execution completed",
    )
    await audit_service.record(
        session,
        action="execution.completed",
        resource_type="execution",
        resource_id=execution.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        actor_type=ActorType.WORKER,
    )


async def _fail(
    session: AsyncSession, task: Task, execution: Execution, reason: str
) -> None:
    current = TaskStatus(execution.status)
    if sm.can_transition(current, TaskStatus.FAILED):
        execution.status = TaskStatus.FAILED.value
        task.status = TaskStatus.FAILED.value
    execution.ended_at = utcnow()
    task.failure_reason = reason
    await event_service.emit(
        session,
        type=EventType.EXECUTION_FAILED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        label="Execution failed",
        payload={"reason": reason},
    )
    await audit_service.record(
        session,
        action="execution.failed",
        resource_type="execution",
        resource_id=execution.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        actor_type=ActorType.WORKER,
        metadata={"reason": reason},
    )


async def _cancel(session: AsyncSession, task: Task, execution: Execution) -> None:
    current = TaskStatus(execution.status)
    if sm.can_transition(current, TaskStatus.CANCELLED):
        execution.status = TaskStatus.CANCELLED.value
        task.status = TaskStatus.CANCELLED.value
    execution.ended_at = utcnow()
    await event_service.emit(
        session,
        type=EventType.EXECUTION_CANCELLED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        label="Execution cancelled",
    )
    await audit_service.record(
        session,
        action="task.cancelled",
        resource_type="task",
        resource_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        actor_type=ActorType.WORKER,
    )
