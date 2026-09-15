"""Phase 6: real verification mapping + full synthetic E2E.

Two things are proven here against the REAL AI/ML mission (out-of-process,
:8770):

  1. test_real_verification_integration — the Control Plane persists an
     authoritative VerificationRun (+ per-check rows) derived ONLY from the
     mission report, and gates COMPLETE on it. Tool success is never treated as
     business success; verification is never faked.

  2. test_real_e2e_through_worker_and_sse — a full run driven exactly like a
     client would: POST /tasks -> the worker (handle_job) plans + executes the
     real mission -> the task reaches a terminal state -> events are readable
     over the SSE-backed events endpoint with a monotonic, gap-free sequence
     and reconnect replay works.

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


async def _drain_queue():
    from app.workers.execution_worker import handle_job
    from app.workers.queue import get_queue

    queue = get_queue()
    for _ in range(50):
        job = await queue.dequeue(timeout=0.05)
        if job is None:
            break
        await handle_job(job)


async def _plan_and_execute(goal: str):
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
        if execution.status in ("RUNNING", "RECOVERY"):
            await execution_service.advance(session, task, execution)
        return task.id, execution.id, task.status


@pytest.mark.asyncio
async def test_real_verification_integration(db_reset, seeded, integration_mode):
    from app.db.session import session_scope
    from app.domain.enums import TaskStatus, VerificationStatus
    from app.models.execution import Execution
    from app.models.verification import VerificationCheckModel, VerificationRun
    from sqlalchemy import select

    task_id, execution_id, task_status = await _plan_and_execute(
        "Prepare a weekly operations summary"
    )

    async with session_scope() as session:
        runs = (
            await session.execute(
                select(VerificationRun).where(
                    VerificationRun.execution_id == execution_id
                )
            )
        ).scalars().all()

        # An authoritative verification record was persisted (not just events).
        assert len(runs) == 1, runs
        run = runs[0]

        checks = (
            await session.execute(
                select(VerificationCheckModel).where(
                    VerificationCheckModel.verification_run_id == run.id
                )
            )
        ).scalars().all()
        # Named checks were derived from the mission report.
        assert len(checks) >= 1
        check_ids = {c.check_id for c in checks}
        # The document mission carries a document_verified signal.
        assert "document_verified" in check_ids or "mission_verified" in check_ids

        # The run verdict, the execution verification_status, and the task
        # terminal state are mutually consistent — CP gated COMPLETE on the run.
        execution = await session.get(Execution, execution_id)
        assert execution.verification_status == run.status

        if run.status == VerificationStatus.PASSED.value:
            assert all(c.passed for c in checks)
            assert task_status == TaskStatus.COMPLETE.value
        else:
            # A failed/awaiting run must NOT have produced a COMPLETE task.
            assert task_status != TaskStatus.COMPLETE.value


@pytest.mark.asyncio
async def test_real_e2e_through_worker_and_sse(client, seeded, integration_mode):
    # 1. Create the task over HTTP, exactly like a client.
    r = await client.post(
        "/api/v1/tasks",
        json={
            "workspace_id": "ws_operations",
            "goal": "Prepare a weekly operations summary",
        },
    )
    assert r.status_code == 201
    task_id = r.json()["task_id"]
    execution_id = r.json()["execution_id"]

    # 2. The worker plans + executes the real mission.
    await _drain_queue()

    # 3. The task reached an honest terminal (or approval) state.
    r = await client.get(f"/api/v1/tasks/{task_id}")
    assert r.status_code == 200
    status = r.json()["status"]
    assert status in ("COMPLETE", "AWAITING_APPROVAL", "FAILED"), status

    # 4. A validated plan produced by the real AI/ML runtime exists.
    r = await client.get(f"/api/v1/tasks/{task_id}/plans")
    plans = r.json()
    assert len(plans) >= 1
    assert plans[-1]["validation_status"] == "VALIDATED"

    # 5. Events are readable over the SSE-backed endpoint with a monotonic,
    #    gap-free sequence, and include real translated mission events.
    r = await client.get(f"/api/v1/executions/{execution_id}/events?after=0")
    events = r.json()
    seqs = [e["sequence"] for e in events]
    assert seqs == sorted(seqs)
    assert seqs == list(range(1, len(seqs) + 1)), seqs

    translated = [
        e for e in events
        if isinstance(e.get("payload"), dict) and e["payload"].get("source") == "ai-ml"
    ]
    assert len(translated) >= 1

    # 6. Reconnect replay: after a mid sequence returns only later events.
    if len(seqs) >= 2:
        mid = seqs[len(seqs) // 2]
        r = await client.get(
            f"/api/v1/executions/{execution_id}/events?after={mid}"
        )
        replayed = r.json()
        assert all(e["sequence"] > mid for e in replayed)

    # 7. On a verified completion, artifacts and a complete milestone exist.
    if status == "COMPLETE":
        types = {e["type"] for e in events}
        assert "execution.completed" in types
        r = await client.get(f"/api/v1/artifacts?task_id={task_id}")
        assert r.json()["total"] >= 1
