"""Agent runtime interface (backend <-> ML #1 boundary).

Agents PROPOSE structured actions; they do not execute them. The control plane
validates and executes proposed actions through the tool runtime.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.agents import AgentRunRequest, AgentRunResult


class AgentRuntime(Protocol):
    async def run_step(self, request: AgentRunRequest) -> AgentRunResult: ...
