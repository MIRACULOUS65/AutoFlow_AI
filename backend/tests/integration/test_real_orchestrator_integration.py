"""Phase 4: real orchestrator / planning integration.

Drives the planning phase through the REAL AI/ML runtime (out-of-process on
:8770) instead of the mock orchestrator, then asserts the Control Plane
validated and persisted the derived plan exactly as it does for the mock.

The AI/ML server must be running for this test. If it is not reachable the
test is skipped (so the mock baseline stays green without the server), never
faked. Start it with:

    cd ai-ml
    .\\.venv\\Scripts\\python.exe -c "from autoflow_ai.server.app import run_server; run_server(port=8770)"
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
    """Flip the intelligence seam to the real AI/ML runtime for one test.

    Patches the cached settings object and clears the runtime lru_cache so the
    next get_intelligence_runtime() returns RealAiMlRuntime.
    """
    from app import runtime

    monkeypatch.setattr(settings, "intelligence_mode", "integration")
    monkeypatch.setattr(settings, "ai_ml_enabled", True)
    monkeypatch.setattr(settings, "ai_ml_use_model", False)
    runtime.get_intelligence_runtime.cache_clear()
    assert settings.use_real_intelligence is True
    yield
    runtime.get_intelligence_runtime.cache_clear()


async def _run_planning_for(goal: str):
    """Create a task+execution directly and run just the planning phase."""
    from app.db.base import new_id
    from app.db.session import session_scope
    from app.models.execution import Execution
    from app.models.task import Task
    from app.services import planning_service

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
        return task.id, execution.id, task.status


@pytest.mark.asyncio
async def test_real_orchestrator_integration(db_reset, seeded, integration_mode):
    from app.db.session import session_scope
    from app.domain.enums import PlanValidationStatus
    from app.models.plan import TaskPlan, TaskStep
    from sqlalchemy import select

    task_id, execution_id, task_status = await _run_planning_for(
        "Prepare a weekly operations summary"
    )

    # Planning drove past PLANNING/VALIDATING to a live state, never FAILED.
    assert task_status in ("RUNNING", "AWAITING_APPROVAL"), task_status

    async with session_scope() as session:
        plan = (
            await session.execute(
                select(TaskPlan).where(TaskPlan.task_id == task_id)
            )
        ).scalar_one()

        # The plan was produced by the real AI/ML runtime and CP validated it.
        assert plan.generated_by == "ai-ml"
        assert plan.validation_status == PlanValidationStatus.VALIDATED.value
        # The mission id is carried through so execution can reconcile later.
        assert plan.risk_summary.get("source") == "ai-ml"
        assert isinstance(plan.risk_summary.get("mission_id"), str)
        assert plan.risk_summary["mission_id"]

        steps = (
            await session.execute(
                select(TaskStep).where(TaskStep.plan_id == plan.id).order_by(TaskStep.index)
            )
        ).scalars().all()

        # Steps were derived from the real mission trace and persisted.
        assert len(steps) >= 1
        # Dependencies are internally consistent (CP validation guarantee).
        step_ids = {s.id for s in steps}
        for s in steps:
            for dep in s.dependencies:
                assert dep in step_ids
        # Indices are contiguous from 1.
        assert [s.index for s in steps] == list(range(1, len(steps) + 1))


@pytest.mark.asyncio
async def test_mock_still_default_without_integration(db_reset, seeded):
    """Sanity: with integration off, planning uses the mock orchestrator."""
    from app.db.session import session_scope
    from app.models.plan import TaskPlan
    from sqlalchemy import select

    assert settings.use_real_intelligence is False

    task_id, _execution_id, task_status = await _run_planning_for(
        "Create my weekly operations report"
    )
    assert task_status in ("RUNNING", "AWAITING_APPROVAL")

    async with session_scope() as session:
        plan = (
            await session.execute(
                select(TaskPlan).where(TaskPlan.task_id == task_id)
            )
        ).scalar_one()
        assert plan.generated_by == "mock-orchestrator"
