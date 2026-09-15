"""Phase 7: approval convergence against the REAL AI/ML mission.

A high-risk external action (sending the verified report) must be approved by a
human before it happens. This proves the convergence end to end over HTTP:

  gated goal -> mission runs to the pre-send verified state and PARKS ->
  Control Plane raises a real Approval bound to the send action's hash and
  enters AWAITING_APPROVAL -> approve -> the completing (authorized) mission
  runs, performs the send + independent verification -> COMPLETE.

And the reject path: reject -> BLOCKED, no external send performed.

The Control Plane is the approval authority; the AI/ML mission never sends
before the CP records approval. Skipped if the AI/ML server is not reachable.
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
    for _ in range(80):
        job = await queue.dequeue(timeout=0.05)
        if job is None:
            break
        await handle_job(job)


# A goal with an explicit external send triggers the approval gate.
_GATED_GOAL = "Prepare the weekly operations summary and send it to the reviewer"


@pytest.mark.asyncio
async def test_real_approval_convergence(client, seeded, integration_mode):
    # 1. Create a gated task.
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": _GATED_GOAL},
    )
    assert r.status_code == 201
    task_id = r.json()["task_id"]
    execution_id = r.json()["execution_id"]

    # 2. Plan + run the gated mission; it parks awaiting approval.
    await _drain_queue()

    r = await client.get(f"/api/v1/tasks/{task_id}")
    assert r.json()["status"] == "AWAITING_APPROVAL", r.json()["status"]

    # 3. A real pending approval exists, bound to a send action hash.
    r = await client.get("/api/v1/approvals?status=PENDING")
    ours = [a for a in r.json()["items"] if a["task_id"] == task_id]
    assert len(ours) == 1
    approval_id = ours[0]["id"]

    r = await client.get(f"/api/v1/approvals/{approval_id}")
    detail = r.json()
    assert detail["action_hash"].startswith("sha256:")
    assert detail["risk_class"] == "HIGH"

    # 4. No completion event before approval (send has NOT happened).
    r = await client.get(f"/api/v1/executions/{execution_id}/events?after=0")
    before_types = {e["type"] for e in r.json()}
    assert "execution.completed" not in before_types
    assert "approval.requested" in before_types

    # 5. Approve -> the completing (authorized) mission runs to completion.
    r = await client.post(
        f"/api/v1/approvals/{approval_id}/approve", json={"reason": "ok to send"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"

    await _drain_queue()

    r = await client.get(f"/api/v1/tasks/{task_id}")
    assert r.json()["status"] == "COMPLETE", r.json()["status"]

    # 6. The canonical stream now has approval.granted and a single terminal
    #    completion, in order, with monotonic gap-free sequence.
    r = await client.get(f"/api/v1/executions/{execution_id}/events?after=0")
    events = r.json()
    seqs = [e["sequence"] for e in events]
    assert seqs == sorted(seqs)
    assert seqs == list(range(1, len(seqs) + 1)), seqs
    types = [e["type"] for e in events]
    assert "approval.requested" in types
    assert "approval.granted" in types
    assert "execution.completed" in types
    # approval precedes completion (send only after approval).
    assert types.index("approval.granted") < types.index("execution.completed")

    # 7. Verified outcome + artifacts exist.
    r = await client.get(f"/api/v1/artifacts?task_id={task_id}")
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_real_approval_reject_blocks_send(client, seeded, integration_mode):
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": _GATED_GOAL},
    )
    task_id = r.json()["task_id"]
    execution_id = r.json()["execution_id"]
    await _drain_queue()

    r = await client.get(f"/api/v1/tasks/{task_id}")
    assert r.json()["status"] == "AWAITING_APPROVAL"

    r = await client.get("/api/v1/approvals?status=PENDING")
    approval_id = [a for a in r.json()["items"] if a["task_id"] == task_id][0]["id"]

    # Reject -> BLOCKED, no send performed.
    r = await client.post(
        f"/api/v1/approvals/{approval_id}/reject", json={"reason": "do not send"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    await _drain_queue()

    r = await client.get(f"/api/v1/tasks/{task_id}")
    assert r.json()["status"] == "BLOCKED"

    # No completion ever emitted (the external action never happened).
    r = await client.get(f"/api/v1/executions/{execution_id}/events?after=0")
    types = {e["type"] for e in r.json()}
    assert "execution.completed" not in types
    assert "approval.rejected" in types
