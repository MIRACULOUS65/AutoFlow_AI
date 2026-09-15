"""Execution event endpoints — polling list + SSE stream with reconnect replay."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Header, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.api.deps import PrincipalDep
from app.api.serializers import event_out
from app.core.errors import not_found, unauthenticated
from app.core.security import Principal, resolve_token
from app.db.session import session_scope
from app.repositories import events as events_repo
from app.repositories import executions as exec_repo
from app.schemas.events import ExecutionEvent

router = APIRouter(tags=["events"])

# Terminal statuses at which the SSE stream can close cleanly.
_TERMINAL = {"COMPLETE", "FAILED", "CANCELLED", "EXPIRED"}


@router.get("/executions/{execution_id}/events", response_model=list[ExecutionEvent])
async def list_events(
    execution_id: str,
    principal: PrincipalDep,
    after: int = Query(0, ge=0),
) -> list[ExecutionEvent]:
    """Polling access + reconnect replay (?after=<sequence>)."""
    async with session_scope() as session:
        ex = await exec_repo.get_execution(
            session, execution_id, organization_id=principal.organization_id
        )
        if ex is None:
            raise not_found("Execution", execution_id)
        rows = await events_repo.list_events_after(session, execution_id, after=after)
        return [event_out(e) for e in rows]


@router.get("/executions/{execution_id}/stream")
async def stream_events(
    request: Request,
    execution_id: str,
    after: int = Query(0, ge=0),
    authorization: str | None = Header(default=None),
    access_token: str | None = Query(default=None),
) -> EventSourceResponse:
    """SSE stream. Replays missing events (?after=seq), then tails live events,
    sending keepalives, and closes cleanly at a terminal status.

    Auth: the browser ``EventSource`` API cannot set request headers, so this
    endpoint also accepts the token via the ``access_token`` query parameter
    (falling back to the Authorization header for non-browser clients). This is
    the standard SSE auth pattern; the token is the same mock bearer token.
    """

    # Resolve the principal from header OR query token (EventSource has no headers).
    raw = authorization
    if raw and raw.lower().startswith("bearer "):
        raw = raw[7:]
    token = raw or access_token
    if not token:
        raise unauthenticated("Missing credentials for event stream.")
    principal: Principal | None = resolve_token(token)
    if principal is None:
        raise unauthenticated("Invalid or expired token.")

    # Authorize before opening the stream.
    async with session_scope() as session:
        ex = await exec_repo.get_execution(
            session, execution_id, organization_id=principal.organization_id
        )
        if ex is None:
            raise not_found("Execution", execution_id)

    async def event_generator() -> AsyncGenerator[dict, None]:
        last_seq = after
        idle_ticks = 0
        while True:
            if await request.is_disconnected():
                break

            async with session_scope() as session:
                rows = await events_repo.list_events_after(
                    session, execution_id, after=last_seq
                )
                ex = await exec_repo.get_execution(session, execution_id)

            if rows:
                idle_ticks = 0
                for e in rows:
                    payload = event_out(e).model_dump(mode="json")
                    last_seq = e.sequence
                    yield {
                        "event": e.type,
                        "id": str(e.sequence),
                        "data": json.dumps(payload),
                    }
            else:
                idle_ticks += 1

            # Close cleanly once terminal and the client has caught up.
            if ex is not None and ex.status in _TERMINAL and not rows:
                yield {"event": "stream.end", "data": json.dumps({"status": ex.status})}
                break

            # Keepalive comment roughly every ~15s of idleness (~0.4s/tick).
            if idle_ticks and idle_ticks % 37 == 0:
                yield {"comment": "keepalive"}

            await asyncio.sleep(0.4)

    return EventSourceResponse(event_generator())
