"""Durable-ish job queue abstraction.

Two implementations behind one interface:

* InProcessQueue — an asyncio.Queue for zero-infra dev/demo. Jobs are consumed
  by an inline worker task in the same process.
* RedisQueue — a Redis list for the production path. Jobs are idempotent so a
  crashed worker can be replaced safely.

The queue never holds authoritative workflow state — PostgreSQL does. Jobs are
just triggers to advance a durably-persisted execution.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol


class JobQueue(Protocol):
    async def enqueue(self, job: dict[str, Any]) -> None: ...

    async def dequeue(self, timeout: float = 1.0) -> dict[str, Any] | None: ...


class InProcessQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def enqueue(self, job: dict[str, Any]) -> None:
        await self._queue.put(job)

    async def dequeue(self, timeout: float = 1.0) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class RedisQueue:
    """Redis list backed queue (BLPOP/RPUSH). Requires redis.asyncio."""

    KEY = "autoflow:jobs"

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis  # local import so redis stays optional

        self._client = redis.from_url(url, decode_responses=True)

    async def enqueue(self, job: dict[str, Any]) -> None:
        await self._client.rpush(self.KEY, json.dumps(job))

    async def dequeue(self, timeout: float = 1.0) -> dict[str, Any] | None:
        result = await self._client.blpop([self.KEY], timeout=int(max(1, timeout)))
        if result is None:
            return None
        _key, payload = result
        return json.loads(payload)


_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        from app.core.config import settings

        if settings.redis_url:
            _queue = RedisQueue(settings.redis_url)
        else:
            _queue = InProcessQueue()
    return _queue


def reset_queue() -> None:
    global _queue
    _queue = None
