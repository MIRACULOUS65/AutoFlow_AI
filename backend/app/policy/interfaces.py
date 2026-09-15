"""Policy engine interface. Authorization is independent of retrieval relevance."""

from __future__ import annotations

from typing import Any, Protocol

from app.schemas.agents import PolicyDecision


class PolicyEngine(Protocol):
    async def evaluate(
        self,
        *,
        actor: str,
        workspace_id: str,
        action: str,
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision: ...
