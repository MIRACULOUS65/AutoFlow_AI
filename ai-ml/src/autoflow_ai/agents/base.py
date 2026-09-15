"""Specialist agent base interface."""

from __future__ import annotations

from ..planning.models import AgentType
from .models import AgentContext, AgentResult, AgentStatus


class SpecialistAgent:
    """Base class for specialist agents.

    Subclasses implement :meth:`propose` to return a structured
    :class:`AgentResult`. The default implementation is a safe no-op so partial
    agents never fake work. Agents propose; the runtime executes.
    """

    agent_type: AgentType
    capabilities: tuple[str, ...] = ()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def propose(self, context: AgentContext) -> AgentResult:  # pragma: no cover - overridden
        return AgentResult(
            status=AgentStatus.NOOP,
            reasoning_summary=f"{self.agent_type} produced no action",
            confidence=0.0,
        )
