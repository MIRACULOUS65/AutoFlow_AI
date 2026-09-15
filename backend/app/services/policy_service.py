"""Policy service — thin wrapper over the configured PolicyEngine."""

from __future__ import annotations

from typing import Any

from app.runtime import get_policy_engine
from app.schemas.agents import PolicyDecision


async def evaluate(
    *,
    actor: str,
    workspace_id: str,
    action: str,
    resource: str | None = None,
    context: dict[str, Any] | None = None,
) -> PolicyDecision:
    engine = get_policy_engine()
    return await engine.evaluate(
        actor=actor,
        workspace_id=workspace_id,
        action=action,
        resource=resource,
        context=context,
    )
