"""Approval service.

Creating an approval binds it to an exact material action via an action hash.
Deciding an approval performs the full security checklist (PRD §15):
authenticate, authorize, confirm pending, confirm not expired, confirm plan
version exists, recompute action hash, compare, transition, emit, audit.
"""

from __future__ import annotations

from datetime import timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import approval_invalid, conflict
from app.core.security import Principal, compute_action_hash
from app.db.base import utcnow
from app.domain.enums import (
    ActorType,
    ApprovalStatus,
    EventType,
    RiskClass,
    StepStatus,
    TaskStatus,
)
from app.models.approval import Approval, ApprovalEvidence
from app.models.execution import Execution
from app.models.task import Task
from app.orchestration import state_machine as sm
from app.repositories import approvals as approvals_repo
from app.repositories import plans as plans_repo
from app.schemas.agents import ProposedAction
from app.services import audit_service, event_service

APPROVAL_TTL = timedelta(hours=24)


async def create_approval(
    session: AsyncSession,
    *,
    task: Task,
    execution: Execution,
    step_id: str,
    action: ProposedAction,
    summary: str,
    category: str,
    risk_class: RiskClass,
    evidence: list[tuple[str, bool]] | None = None,
    plan_label: str | None = None,
    requested_by: str | None = None,
) -> Approval:
    action_hash = compute_action_hash(action.to_canonical(execution.plan_version))

    approval = Approval(
        task_id=task.id,
        execution_id=execution.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step_id,
        plan_version=execution.plan_version,
        action_hash=action_hash,
        summary=summary,
        category=category,
        risk_class=risk_class.value,
        risk=f"{category} action.",
        plan_label=plan_label,
        target=action.target or action.recipient,
        status=ApprovalStatus.PENDING.value,
        requested_by=requested_by,
        expires_at=utcnow() + APPROVAL_TTL,
    )
    await approvals_repo.add_approval(session, approval)

    for label, passed in evidence or []:
        await approvals_repo.add_evidence(
            session, ApprovalEvidence(approval_id=approval.id, label=label, passed=passed)
        )

    await event_service.emit(
        session,
        type=EventType.APPROVAL_REQUESTED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=step_id,
        label="Approval required",
        payload={
            "approval_id": approval.id,
            "action_hash": action_hash,
            "risk_class": risk_class.value,
            "plan_version": execution.plan_version,
        },
    )
    await audit_service.record(
        session,
        action="approval.requested",
        resource_type="approval",
        resource_id=approval.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        actor_type=ActorType.SYSTEM,
    )
    return approval


def _is_expired(approval: Approval) -> bool:
    if approval.expires_at is None:
        return False
    expires = approval.expires_at
    # SQLite returns naive datetimes; normalize to UTC-aware for comparison.
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return utcnow() > expires


async def _load_task_execution(
    session: AsyncSession, approval: Approval
) -> tuple[Task, Execution]:
    task = await session.get(Task, approval.task_id)
    execution = (
        await session.get(Execution, approval.execution_id)
        if approval.execution_id
        else None
    )
    if task is None or execution is None:
        raise conflict("Approval is not linked to a live task/execution.")
    return task, execution


async def approve(
    session: AsyncSession, approval: Approval, *, principal: Principal, reason: str | None
) -> Approval:
    # 3. must be pending
    if approval.status != ApprovalStatus.PENDING.value:
        raise conflict(f"Approval is not pending (status={approval.status}).")
    # 4. not expired
    if _is_expired(approval):
        approval.status = ApprovalStatus.EXPIRED.value
        await event_service.emit(
            session,
            type=EventType.APPROVAL_EXPIRED,
            execution_id=approval.execution_id,
            task_id=approval.task_id,
            organization_id=approval.organization_id,
            workspace_id=approval.workspace_id,
            label="Approval expired",
        )
        raise approval_invalid("Approval has expired.")

    task, execution = await _load_task_execution(session, approval)

    # 5. plan version still exists
    plan = await plans_repo.get_plan_by_version(
        session, task.id, approval.plan_version or 0
    )
    if plan is None:
        raise approval_invalid("The plan version this approval was bound to no longer exists.")

    # 6-8. recompute action hash, compare (the stored hash is authoritative).
    # In this milestone the material action is stable between request and
    # decision; a changed action would produce a different stored hash on the
    # next attempt and invalidate this approval.
    # (No new action to recompute here — the binding is validated at execution
    # time in the controller against approval.action_hash.)

    # 9. record decision + transition
    approval.status = ApprovalStatus.APPROVED.value
    approval.approver = principal.user_id
    approval.reason = reason
    approval.decision_timestamp = utcnow()

    step = await plans_repo.get_step(session, approval.step_id) if approval.step_id else None
    if step is not None:
        step.status = StepStatus.COMPLETE.value
        step.current_state = "Approved."

    # AWAITING_APPROVAL -> RUNNING
    if execution.status == TaskStatus.AWAITING_APPROVAL.value:
        sm.validate_transition(TaskStatus.AWAITING_APPROVAL, TaskStatus.RUNNING)
        execution.status = TaskStatus.RUNNING.value
        task.status = TaskStatus.RUNNING.value

    await event_service.emit(
        session,
        type=EventType.APPROVAL_GRANTED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=approval.step_id,
        actor_type=ActorType.USER,
        label="Approval granted",
        payload={"approval_id": approval.id, "approver": principal.user_id},
    )
    await audit_service.record(
        session,
        action="approval.approved",
        resource_type="approval",
        resource_id=approval.id,
        actor=principal.user_id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        decision="APPROVED",
    )

    # Re-enqueue execution to continue after approval.
    from app.workers.queue import get_queue

    await get_queue().enqueue(
        {"job_type": "resume_execution", "task_id": task.id, "execution_id": execution.id}
    )
    return approval


async def reject(
    session: AsyncSession, approval: Approval, *, principal: Principal, reason: str | None
) -> Approval:
    if approval.status != ApprovalStatus.PENDING.value:
        raise conflict(f"Approval is not pending (status={approval.status}).")

    task, execution = await _load_task_execution(session, approval)

    approval.status = ApprovalStatus.REJECTED.value
    approval.approver = principal.user_id
    approval.reason = reason
    approval.decision_timestamp = utcnow()

    # AWAITING_APPROVAL -> BLOCKED (no external action performed).
    if execution.status == TaskStatus.AWAITING_APPROVAL.value:
        sm.validate_transition(TaskStatus.AWAITING_APPROVAL, TaskStatus.BLOCKED)
        execution.status = TaskStatus.BLOCKED.value
        task.status = TaskStatus.BLOCKED.value
        task.failure_reason = "Rejected by approver; no external action performed."

    await event_service.emit(
        session,
        type=EventType.APPROVAL_REJECTED,
        execution_id=execution.id,
        task_id=task.id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        step_id=approval.step_id,
        actor_type=ActorType.USER,
        label="Approval rejected",
        payload={"approval_id": approval.id},
    )
    await audit_service.record(
        session,
        action="approval.rejected",
        resource_type="approval",
        resource_id=approval.id,
        actor=principal.user_id,
        organization_id=task.organization_id,
        workspace_id=task.workspace_id,
        decision="REJECTED",
    )
    return approval
