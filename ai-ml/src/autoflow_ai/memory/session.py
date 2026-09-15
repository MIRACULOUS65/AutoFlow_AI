"""Session memory store (in-process, bounded, serializable).

Session memory is short-lived and must never become permanent workflow memory.
"""

from __future__ import annotations

from .models import SessionMemory


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionMemory] = {}

    def create(self, task_id: str, **kwargs) -> SessionMemory:
        session = SessionMemory(task_id=task_id, **kwargs)
        self._sessions[task_id] = session
        return session

    def get(self, task_id: str) -> SessionMemory | None:
        return self._sessions.get(task_id)

    def update(self, task_id: str, **fields) -> SessionMemory:
        session = self._sessions[task_id]
        for k, v in fields.items():
            setattr(session, k, v)
        return session

    def delete(self, task_id: str) -> None:
        self._sessions.pop(task_id, None)

    def snapshot(self, task_id: str) -> dict:
        return self._sessions[task_id].snapshot()

    def restore(self, data: dict) -> SessionMemory:
        session = SessionMemory.restore(data)
        self._sessions[session.task_id] = session
        return session

    def count(self) -> int:
        return len(self._sessions)
