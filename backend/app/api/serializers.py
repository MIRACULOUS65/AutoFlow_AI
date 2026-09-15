"""Model -> schema assemblers.

Kept out of routes and services so the mapping between persistence and API
contracts lives in one place. Aligns backend rows with the frontend domain
model (PRD §8, §91).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval
from app.models.artifact import Artifact
from app.models.event import Event
from app.models.execution import Execution
from app.models.plan import TaskPlan, TaskStep
from app.models.task import Task
from app.repositories import approvals as approvals_repo
from app.repositories import artifacts as artifacts_repo
from app.repositories import plans as plans_repo
from app.repositories import tasks as tasks_repo
from app.schemas.approval import ApprovalDetail, ApprovalSummary, EvidenceItem
from app.schemas.artifacts import ArtifactSummary
from app.schemas.events import ExecutionEvent
from app.schemas.execution import ExecutionDetail, ExecutionSummary
from app.schemas.plan import PlanDetail, PlanStepOut, PlanSummary
from app.schemas.task import TaskAttachmentOut, TaskDetail, TaskSummary


def _duration_ms(model) -> int:
    started = getattr(model, "started_at", None)
    ended = getattr(model, "ended_at", None) or getattr(model, "completed_at", None)
    if started and ended:
        return int((ended - started).total_seconds() * 1000)
    return 0


def task_summary(task: Task) -> TaskSummary:
    return TaskSummary(
        id=task.id,
        workspace_id=task.workspace_id,
        name=task.name,
        goal=task.goal,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        execution_id=task.current_execution_id,
        workflow_id=task.workflow_id,
        plan_version=f"v{task.current_plan_version}" if task.current_plan_version else "v0",
        assigned_agent_id=task.assigned_agent_id,
        duration_ms=_duration_ms(task),
        verification=task.verification_status,
        priority=task.priority,
    )


async def task_detail(session: AsyncSession, task: Task) -> TaskDetail:
    summary = task_summary(task)
    attachments = await tasks_repo.get_attachments(session, task.id)
    steps = (
        await plans_repo.get_steps_for_task_version(
            session, task.id, task.current_plan_version
        )
        if task.current_plan_version
        else []
    )
    artifacts = await artifacts_repo.list_artifacts(
        session, organization_id=task.organization_id, task_id=task.id, limit=200
    )
    appr, _ = await approvals_repo.list_approvals(
        session, organization_id=task.organization_id, task_id=task.id, limit=200
    )
    return TaskDetail(
        **summary.model_dump(),
        normalized_goal=task.normalized_goal,
        failure_reason=task.failure_reason,
        attachments=[
            TaskAttachmentOut(
                id=a.id, filename=a.filename, mime_type=a.mime_type, size=a.size
            )
            for a in attachments
        ],
        artifact_ids=[a.id for a in artifacts[0]],
        approval_ids=[a.id for a in appr],
        step_ids=[s.id for s in steps],
    )


def step_out(step: TaskStep) -> PlanStepOut:
    return PlanStepOut(
        id=step.id,
        index=step.index,
        title=step.title,
        objective=step.objective,
        agent_id=step.agent_profile,
        status=step.status,
        verification=step.verification_status,
        depends_on=step.dependencies,
        tools=step.allowed_tools,
        expected_state=step.expected_state,
        current_state=step.current_state,
        attempts=step.attempts,
        max_attempts=(step.retry_policy or {}).get("max_attempts", 3),
        requires_approval=step.requires_approval,
        risk_class=step.risk_class,
    )


def execution_summary(execution: Execution, task_name: str | None = None) -> ExecutionSummary:
    return ExecutionSummary(
        id=execution.id,
        task_id=execution.task_id,
        task_name=task_name,
        workspace_id=execution.workspace_id,
        status=execution.status,
        agent_id=execution.agent_id,
        plan_version=execution.plan_version,
        current_step_id=execution.current_step_id,
        attempt_count=execution.attempt_count,
        cancel_requested=execution.cancel_requested,
        started_at=execution.started_at,
        ended_at=execution.ended_at,
        duration_ms=_duration_ms(execution),
        verification=execution.verification_status,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
    )


async def execution_detail(session: AsyncSession, execution: Execution) -> ExecutionDetail:
    task = await session.get(Task, execution.task_id)
    summary = execution_summary(execution, task.name if task else None)
    steps = (
        await plans_repo.get_steps_for_plan(session, execution.plan_id)
        if execution.plan_id
        else []
    )
    artifacts = await artifacts_repo.list_for_execution(session, execution.id)
    return ExecutionDetail(
        **summary.model_dump(),
        plan_id=execution.plan_id,
        version=execution.version,
        budget=execution.budget or None,
        steps=[step_out(s) for s in steps],
        artifact_ids=[a.id for a in artifacts],
    )


def plan_summary(plan: TaskPlan) -> PlanSummary:
    return PlanSummary(
        plan_id=plan.id,
        task_id=plan.task_id,
        version=plan.version,
        validation_status=plan.validation_status,
        required_approvals=plan.required_approvals,
        plan_hash=plan.plan_hash,
        created_at=plan.created_at,
    )


async def plan_detail(session: AsyncSession, plan: TaskPlan) -> PlanDetail:
    steps = await plans_repo.get_steps_for_plan(session, plan.id)
    return PlanDetail(
        **plan_summary(plan).model_dump(),
        risk_summary=plan.risk_summary or {},
        steps=[step_out(s) for s in steps],
    )


def approval_summary(approval: Approval, task_name: str | None = None) -> ApprovalSummary:
    return ApprovalSummary(
        id=approval.id,
        task_id=approval.task_id,
        task_name=task_name,
        workspace_id=approval.workspace_id,
        execution_id=approval.execution_id,
        step_id=approval.step_id,
        plan_version=approval.plan_version,
        action=approval.summary,
        category=approval.category,
        risk_class=approval.risk_class,
        status=approval.status,
        requested_at=approval.requested_at,
        resolved_at=approval.decision_timestamp,
        expires_at=approval.expires_at,
    )


async def approval_detail(session: AsyncSession, approval: Approval) -> ApprovalDetail:
    task = await session.get(Task, approval.task_id)
    evidence = await approvals_repo.get_evidence(session, approval.id)
    base = approval_summary(approval, task.name if task else None)
    return ApprovalDetail(
        **base.model_dump(),
        action_hash=approval.action_hash,
        target=approval.target,
        attachment=approval.attachment,
        plan_label=approval.plan_label,
        risk=approval.risk,
        reason=approval.reason,
        requested_by=approval.requested_by,
        approver=approval.approver,
        evidence=[
            EvidenceItem(id=e.id, label=e.label, passed=e.passed) for e in evidence
        ],
    )


def artifact_summary(artifact: Artifact) -> ArtifactSummary:
    return ArtifactSummary(
        id=artifact.id,
        name=artifact.name,
        kind=artifact.kind,
        mime_type=artifact.mime_type,
        size_bytes=artifact.size_bytes,
        workspace_id=artifact.workspace_id,
        execution_id=artifact.execution_id,
        task_id=artifact.task_id,
        workflow_id=artifact.workflow_id,
        verification_status=artifact.verification_status,
        content_hash=artifact.content_hash,
        created_by_agent=artifact.created_by_agent,
        created_at=artifact.created_at,
    )


def event_out(event: Event) -> ExecutionEvent:
    return ExecutionEvent(
        id=event.id,
        type=event.type,
        organization_id=event.organization_id,
        workspace_id=event.workspace_id,
        task_id=event.task_id,
        execution_id=event.execution_id,
        step_id=event.step_id,
        agent_run_id=event.agent_run_id,
        model_call_id=event.model_call_id,
        tool_call_id=event.tool_call_id,
        verification_id=event.verification_id,
        sequence=event.sequence,
        at=event.timestamp,
        actor_type=event.actor_type,
        label=event.label,
        payload=event.payload or {},
        trace_id=event.trace_id,
    )
