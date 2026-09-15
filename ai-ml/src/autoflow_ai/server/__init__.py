"""Local orchestration API + minimal frontend for AutoFlow AI.

A dependency-free (Python stdlib ``http.server``) local API that exposes the
existing AI/ML runtime to a browser frontend WITHOUT the frontend ever calling
agent classes directly. It reuses the orchestrator / society / lab — no second
runtime, no second gateway. Binds to localhost only.
"""

from __future__ import annotations

from .events import MissionEvent, MissionEventBus, EventType
from .missions import MissionRecord, MissionRegistry
from .app import AutoFlowServer, build_server, run_server

__all__ = [
    "MissionEvent",
    "MissionEventBus",
    "EventType",
    "MissionRecord",
    "MissionRegistry",
    "AutoFlowServer",
    "build_server",
    "run_server",
]
