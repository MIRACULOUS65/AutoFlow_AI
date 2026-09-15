import pytest


@pytest.mark.asyncio
async def test_create_task_returns_queued(client):
    r = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "Create my weekly operations report"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "QUEUED"
    assert body["task_id"].startswith("task_")
    assert body["execution_id"].startswith("exec_")


@pytest.mark.asyncio
async def test_create_task_empty_goal_rejected(client):
    r = await client.post("/api/v1/tasks", json={"workspace_id": "ws_operations", "goal": ""})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_task_unauthenticated(client):
    r = await client.post(
        "/api/v1/tasks",
        headers={"Authorization": ""},
        json={"workspace_id": "ws_operations", "goal": "x"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_idempotency_key_returns_same_task(client):
    payload = {"workspace_id": "ws_operations", "goal": "Reconcile invoices"}
    headers = {"Idempotency-Key": "abc-123"}
    r1 = await client.post("/api/v1/tasks", json=payload, headers=headers)
    r2 = await client.post("/api/v1/tasks", json=payload, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["task_id"] == r2.json()["task_id"]


@pytest.mark.asyncio
async def test_idempotency_key_conflict_on_different_body(client):
    headers = {"Idempotency-Key": "dup-1"}
    await client.post("/api/v1/tasks", json={"workspace_id": "ws_operations", "goal": "A"}, headers=headers)
    r = await client.post("/api/v1/tasks", json={"workspace_id": "ws_operations", "goal": "B"}, headers=headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_get_task_not_found(client):
    r = await client.get("/api/v1/tasks/task_does_not_exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_tasks_paginates(client, seeded):
    # Create a task first (the seed no longer provides demo tasks — the UI
    # shows only real data), then confirm it appears in the list.
    create = await client.post(
        "/api/v1/tasks",
        json={"workspace_id": "ws_operations", "goal": "List pagination test task"},
    )
    assert create.status_code == 201

    r = await client.get("/api/v1/tasks?workspace_id=ws_operations")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert body["total"] >= 1
