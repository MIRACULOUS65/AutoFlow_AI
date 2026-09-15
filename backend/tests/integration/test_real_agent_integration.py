"""Phase 5: real agent / mission execution + event translation.

Drives planning AND execution through the REAL AI/ML mission (out-of-process on
:8770), then asserts the Control Plane:
  - observed the real mission (did not re-run tools/verification itself),
  - translated the mission trace into canonical CP events with an authoritative,
    monotonic, gap-free per-execution sequence,
  - reconciled the derived steps and reached an honest terminal state.

Skipped if the AI/ML server is not reachable (mock baseline stays green).
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import settings


def _ai_ml_reachable() -> bool:
    try:
        r = httpx.get(f"{settings.ai_ml_url}/missions", timeout=2.0)
        return r.status_code < 500
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _ai_ml_reachable(),
    reason="AI/ML runtime not reachable on :8770 (start it to run integration tests).",
)


@pytest.fixture
def integration_mode(monkeypatch):
    from app import runtime

    monkeypatch.setattr(settings, "intelligence_mode", "integration")
    monkeypatch.setattr(settings, "ai_ml_enabled", True)
    monkeypatch.setattr(settings, "ai_ml_use_model", False)
    runtime.get_intelligence_runtime.cache_clear()
    assert settings.use_real_intelligence is True
    yield
    runtime.get_intelligence_runtime.cache_clear()


async def _plan_and_execute(goal: str):
    """Run planning then execution against the real mission, like the worker."""
    from app.db.base import new_id
    from app.db.session import session_scope
    from app.models.execution import Execution
    from app.models.task import Task
    from app.services import execution_service, planning_service

    async with session_scope() as session:
        task = Task(
            id=new_id("task"),
            organization_id="org_demo",
            workspace_id="ws_operations",
            created_by="user_demo",
            name=goal[:60],
            goal=goal,
            status="QUEUED",
        )
        session.add(task)
        execution = Execution(
            id=new_id("exec"),
            task_id=task.id,
            organization_id=task.organization_id,
            workspace_id=task.workspace_id,
            status="QUEUED",
        )
        session.add(execution)
        await session.flush()

        await planning_service.run_planning(session, task, execution)
        # Worker continues into execution when planning ended RUNNING/RECOVERY.
        if execution.status in ("RUNNING", "RECOVERY"):
            await execution_service.advance(session, task, execution)
        return task.id, execution.id, task.status


@pytest.mark.asyncio
async def test_real_agent_integration(db_reset, seeded, integration_mode):
    from app.db.session import session_scope
    from app.domain.enums import EventType, StepStatus, TaskStatus
    from app.models.event import Event
    from app.models.plan import TaskPlan, TaskStep
    from sqlalchemy import select

    task_id, execution_id, task_status = await _plan_and_execute(
        "Prepare a weekly operations summary"
    )

    # The mission ran to an honest terminal (or approval) state — never a
    # silent stall in RUNNING.
    assert task_status in (
        TaskStatus.COMPLETE.value,
        TaskStatus.AWAITING_APPROVAL.value,
        TaskStatus.FAILED.value,
    ), task_status

    async with session_scope() as session:
        events = (
            await session.execute(
                select(Event)
                .where(Event.execution_id == execution_id)
                .order_by(Event.sequence)
            )
        ).scalars().all()

        # Authoritative CP sequencing: monotonic, gap-free from 1.
        seqs = [e.sequence for e in events]
        assert seqs == sorted(seqs)
        assert seqs == list(range(1, len(seqs) + 1)), seqs

        types = [e.type for e in events]
        # Planning milestones from the CP itself.
        assert EventType.EXECUTION_STARTED.value in types
        assert EventType.PLAN_CREATED.value in types
        assert EventType.PLAN_VALIDATED.value in types

        # Real translated mission events landed in the canonical stream.
        translated = [
            e for e in events
            if isinstance(e.payload, dict) and e.payload.get("source") == "ai-ml"
        ]
        assert len(translated) >= 1, "no translated AI/ML events reached CP stream"
        translated_types = {e.type for e in translated}
        # The real society run delegates work and verifies it.
        assert EventType.VERIFICATION_PASSED.value in translated_types

        # Exactly one terminal execution event, owned by the CP (no duplicates
        # from the trace copy).
        terminal = [
            e for e in events
            if e.type in (
                EventType.EXECUTION_COMPLETED.value,
                EventType.EXECUTION_FAILED.value,
            )
        ]
        if task_status != TaskStatus.AWAITING_APPROVAL.value:
            assert len(terminal) == 1, [e.type for e in terminal]

        # Steps were reconciled off the mission outcome, not left WAITING.
        plan = (
            await session.execute(
                select(TaskPlan).where(TaskPlan.task_id == task_id)
            )
        ).scalar_one()
        steps = (
            await session.execute(
                select(TaskStep).where(TaskStep.plan_id == plan.id)
            )
        ).scalars().all()
        if task_status == TaskStatus.COMPLETE.value:
            assert all(s.status == StepStatus.COMPLETE.value for s in steps)
