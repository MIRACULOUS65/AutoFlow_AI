import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_version(client):
    r = await client.get("/version")
    body = r.json()
    assert r.status_code == 200
    assert body["api_version"] == "v1"
    assert body["modes"]["orchestrator"] == "mock"


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": ""})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_me_returns_principal(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["user_id"] == "usr_001"
