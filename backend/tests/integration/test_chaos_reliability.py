"""Phase 9: chaos / reliability + honesty guarantees.

These tests assert the system degrades honestly and stays consistent under
adverse conditions. The most important guarantee: when the real AI/ML runtime
is unavailable, the task FAILS honestly — it is never reported COMPLETE or
verified.

The AI/ML-unavailable tests do NOT need a live server (they point at a dead
port on purpose), so they run in any environment. Reconnect/idempotency tests
run on the mock path and need no server either.
"""

from __future__ import annotations

import pytest

from app.core.config import settings


# --------------------------------------------------------------------------
# AI/ML unavailable -> honest failure (integration mode, unreachable runtime)
# --------------------------------------------------------------------------


@pytest.fixture
def integration_mode_dead_backend(monkeypatch):
    """Integration mode pointed at a dead port: the AI/ML runtime is 'down'."""
    from app import runtime

    monkeypatch.setattr(settings, "intelligence_mode", "integration")
    monkeypatch.setattr(settings, "ai_ml_enabled", True)
    monkeypatch.setattr(settings, "ai_ml_url", "http://127.0.0.1:59999")
    monkeypatch.setattr(settings, "ai_ml_timeout_seconds", 3)
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


@pytest.mark.asyncio
async def test_ai_ml_unavailable_fails_honestly(client, seeded, integration_mode_dead_backend):
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "Prepare a weekly operations summary"},
    )
    assert r.status_code == 201
    task_id = r.json()["task_id"]
    execution_id = r.json()["execution_id"]

    await _drain_queue()

    # The task must fail honestly — never COMPLETE, never verified.
    r = await client.get(f"/api/v1/tasks/{task_id}")
    body = r.json()
    assert body["status"] == "FAILED", body["status"]
    assert body.get("verification") in (None, "NONE", "PENDING", "FAILED")

    # No execution.completed event was ever emitted.
    r = await client.get(f"/api/v1/executions/{execution_id}/events?after=0")
    types = {e["type"] for e in r.json()}
    assert "execution.completed" not in types


@pytest.mark.asyncio
async def test_ai_ml_runtime_returns_failed_not_raise(integration_mode_dead_backend):
    """The runtime adapter yields a controlled failed outcome, never raises."""
    from app.db.base import new_id
    from app.intelligence.interfaces import MissionRequest
    from app.runtime import get_intelligence_runtime

    rt = get_intelligence_runtime()
    assert await rt.available() is False

    req = MissionRequest(
        task_id=new_id("task"),
        execution_id=new_id("exec"),
        workspace_id="ws_operations",
        organization_id="org_demo",
        goal="Prepare a weekly operations summary",
    )
    outcome = await rt.run_mission(req)
    assert outcome.status == "FAILED"
    assert outcome.verified is False


# --------------------------------------------------------------------------
# Reconnect replay + worker idempotency (mock path — deterministic, no server)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconnect_replay_returns_only_later_events(client, seeded):
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "Create my weekly operations report"},
    )
    task_id = r.json()["task_id"]
    execution_id = r.json()["execution_id"]
    await _drain_queue()  # runs to AWAITING_APPROVAL in mock mode

    all_events = (await client.get(f"/api/v1/executions/{execution_id}/events?after=0")).json()
    assert len(all_events) >= 2
    seqs = [e["sequence"] for e in all_events]
    assert seqs == list(range(1, len(seqs) + 1))  # gap-free from 1

    mid = seqs[len(seqs) // 2]
    replayed = (
        await client.get(f"/api/v1/executions/{execution_id}/events?after={mid}")
    ).json()
    assert replayed  # there are later events
    assert all(e["sequence"] > mid for e in replayed)
    # Replayed slice is exactly the tail of the full stream (no loss, no dupes).
    assert [e["sequence"] for e in replayed] == [s for s in seqs if s > mid]


@pytest.mark.asyncio
async def test_worker_redelivery_is_idempotent(client, seeded):
    """Re-running a job for a terminal execution must not corrupt state or
    duplicate events (worker restart / at-least-once delivery safety)."""
    from app.db.session import session_scope
    from app.models.execution import Execution
    from app.models.task import Task
    from app.workers.execution_worker import handle_job

    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "Create my weekly operations report"},
    )
    task_id = r.json()["task_id"]
    execution_id = r.json()["execution_id"]
    await _drain_queue()

    before = (await client.get(f"/api/v1/executions/{execution_id}/events?after=0")).json()
    status_before = (await client.get(f"/api/v1/tasks/{task_id}")).json()["status"]

    # Redeliver a plan job for the same task+execution (as a restart might).
    await handle_job(
        {"job_type": "plan_task", "task_id": task_id, "execution_id": execution_id}
    )

    after = (await client.get(f"/api/v1/executions/{execution_id}/events?after=0")).json()
    status_after = (await client.get(f"/api/v1/tasks/{task_id}")).json()["status"]

    # Status unchanged and no event-sequence corruption.
    assert status_after == status_before
    after_seqs = [e["sequence"] for e in after]
    assert after_seqs == list(range(1, len(after_seqs) + 1))
    # Redelivery on a non-QUEUED execution is a no-op (no new events).
    assert len(after) == len(before)


# --------------------------------------------------------------------------
# Tenancy isolation
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenancy_isolation_task_scoped_to_workspace(client, seeded):
    """A task created in one workspace is not listed under another."""
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "Create my weekly operations report"},
    )
    task_id = r.json()["task_id"]

    # Listed under its own workspace.
    r = await client.get("/api/v1/tasks?workspace_id=ws_operations")
    ours = [t for t in r.json()["items"] if t["id"] == task_id]
    assert len(ours) == 1

    # Not listed under a different workspace.
    r = await client.get("/api/v1/tasks?workspace_id=ws_finance")
    assert r.status_code == 200
    leaked = [t for t in r.json()["items"] if t["id"] == task_id]
    assert leaked == []
