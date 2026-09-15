"""Orchestrator interface (backend <-> ML #2 boundary).

The backend calls this to obtain a plan. It knows nothing about how the plan is
produced. A real orchestrator replaces the mock without any API change.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.plan import Plan, PlanFragment, ReplanRequest
from app.schemas.task import TaskRequest


class Orchestrator(Protocol):
    async def create_plan(self, request: TaskRequest) -> Plan: ...

    async def replan(self, request: ReplanRequest) -> PlanFragment: ...
