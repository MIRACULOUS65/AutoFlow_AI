"""Flagship end-to-end flow over HTTP.

Because the inline worker is disabled in tests, we drain the in-process queue
manually (drive the worker deterministically) between API calls.
"""

import pytest


async def _drain_queue():
    """Run every queued job to completion (deterministic, no timing races)."""
    from app.workers.execution_worker import handle_job
    from app.workers.queue import get_queue

    queue = get_queue()
    for _ in range(50):
        job = await queue.dequeue(timeout=0.05)
        if job is None:
            break
        await handle_job(job)


@pytest.mark.asyncio
async def test_flagship_end_to_end(client, seeded):
    # 1. Create the task.
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "Create my weekly operations report"},
    )
    assert r.status_code == 201
    task_id = r.json()["task_id"]
    execution_id = r.json()["execution_id"]

    # 2. Planning + execution runs until it blocks on approval.
    await _drain_queue()

    # 3. Task should now be awaiting approval.
    r = await client.get(f"/api/v1/tasks/{task_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "AWAITING_APPROVAL"

    # 4. A plan exists and is validated.
    r = await client.get(f"/api/v1/tasks/{task_id}/plans")
    plans = r.json()
    assert len(plans) >= 1
    assert plans[-1]["validation_status"] == "VALIDATED"

    # 5. There is a pending approval bound to an action hash.
    r = await client.get("/api/v1/approvals?status=PENDING")
    pending = r.json()["items"]
    ours = [a for a in pending if a["task_id"] == task_id]
    assert len(ours) == 1
    approval_id = ours[0]["id"]

    r = await client.get(f"/api/v1/approvals/{approval_id}")
    assert r.json()["action_hash"].startswith("sha256:")

    # 6. Approve.
    r = await client.post(f"/api/v1/approvals/{approval_id}/approve", json={"reason": "ok"})
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"

    # 7. Execution resumes to completion.
    await _drain_queue()

    r = await client.get(f"/api/v1/tasks/{task_id}")
    assert r.json()["status"] == "COMPLETE"

    # 8. Events are monotonically sequenced and include the key milestones.
    r = await client.get(f"/api/v1/executions/{execution_id}/events?after=0")
    events = r.json()
    seqs = [e["sequence"] for e in events]
    assert seqs == sorted(seqs)
    assert seqs == list(range(1, len(seqs) + 1))
    types = {e["type"] for e in events}
    assert "task.created" in types
    assert "plan.validated" in types
    assert "approval.granted" in types
    assert "execution.completed" in types

    # 9. Reconnect replay: events after a mid sequence return only later ones.
    mid = seqs[len(seqs) // 2]
    r = await client.get(f"/api/v1/executions/{execution_id}/events?after={mid}")
    replayed = r.json()
    assert all(e["sequence"] > mid for e in replayed)

    # 10. Artifacts were produced.
    r = await client.get(f"/api/v1/artifacts?task_id={task_id}")
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_reject_blocks_execution(client, seeded):
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "Create my weekly operations report"},
    )
    task_id = r.json()["task_id"]
    await _drain_queue()

    r = await client.get("/api/v1/approvals?status=PENDING")
    approval_id = [a for a in r.json()["items"] if a["task_id"] == task_id][0]["id"]

    r = await client.post(f"/api/v1/approvals/{approval_id}/reject", json={"reason": "no"})
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    r = await client.get(f"/api/v1/tasks/{task_id}")
    assert r.json()["status"] == "BLOCKED"


@pytest.mark.asyncio
async def test_double_approve_conflict(client, seeded):
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "Create my weekly operations report"},
    )
    task_id = r.json()["task_id"]
    await _drain_queue()
    r = await client.get("/api/v1/approvals?status=PENDING")
    approval_id = [a for a in r.json()["items"] if a["task_id"] == task_id][0]["id"]

    r1 = await client.post(f"/api/v1/approvals/{approval_id}/approve")
    assert r1.status_code == 200
    r2 = await client.post(f"/api/v1/approvals/{approval_id}/approve")
    assert r2.status_code == 409
