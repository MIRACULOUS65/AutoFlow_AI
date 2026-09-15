"""Configurable mock policy engine (demonstration fixtures, PRD §45).

Rules map an action (tool name) to a risk class and whether approval is
required. These are demonstration policies, not final enterprise policy — the
table is configurable.
"""

from __future__ import annotations

from typing import Any

from app.domain.enums import RiskClass
from app.schemas.agents import PolicyDecision

# action -> (risk_class, requires_approval, category)
_DEFAULT_RULES: dict[str, tuple[RiskClass, bool, str]] = {
    "knowledge.retrieve.mock": (RiskClass.LOW, False, "retrieval"),
    "spreadsheet.create": (RiskClass.LOW, False, "artifact creation"),
    "document.create": (RiskClass.LOW, False, "artifact creation"),
    "filesystem.create": (RiskClass.LOW, False, "artifact creation"),
    "email.prepare": (RiskClass.MEDIUM, False, "communication draft"),
    "email.send.mock": (RiskClass.HIGH, True, "external communication"),
    "email.send": (RiskClass.HIGH, True, "external communication"),
    "message.send": (RiskClass.HIGH, True, "external communication"),
}


class MockPolicyEngine:
    def __init__(self, rules: dict[str, tuple[RiskClass, bool, str]] | None = None) -> None:
        self.rules = rules or dict(_DEFAULT_RULES)

    async def evaluate(
        self,
        *,
        actor: str,
        workspace_id: str,
        action: str,
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        risk, requires_approval, category = self.rules.get(
            action, (RiskClass.LOW, False, "general")
        )
        return PolicyDecision(
            allowed=True,
            requires_approval=requires_approval,
            risk_class=risk,
            category=category,
            reason=(
                "External communication requires explicit approval."
                if requires_approval
                else "Action allowed by workspace policy."
            ),
        )
