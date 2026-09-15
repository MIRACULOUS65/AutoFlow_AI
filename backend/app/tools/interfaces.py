"""Tool runtime interface.

A proposed action only reaches the tool runtime after schema, policy, permission
and (where required) approval validation. No arbitrary function execution from
model output is ever allowed.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.agents import ToolCall, ToolResult


class ToolRuntime(Protocol):
    def is_allowed(self, tool: str) -> bool: ...

    async def execute(self, call: ToolCall) -> ToolResult: ...
