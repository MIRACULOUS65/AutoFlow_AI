"""Agent registry."""

from __future__ import annotations

from ..planning.models import AgentType
from .base import SpecialistAgent
from .specialists import (
    BrowserAutomationAgent,
    CodingAgent,
    CommunicationAgent,
    ComputerAutomationAgent,
    DocumentAgent,
    PresentationAgent,
    QAAgent,
    ResearchAgent,
    SpreadsheetAgent,
)


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[AgentType, SpecialistAgent] = {}

    def register(self, agent: SpecialistAgent) -> None:
        self._agents[agent.agent_type] = agent

    def get(self, agent_type: AgentType) -> SpecialistAgent | None:
        return self._agents.get(agent_type)

    def has(self, agent_type: AgentType) -> bool:
        return agent_type in self._agents

    def known_agent_names(self) -> set[str]:
        return {str(a) for a in self._agents}

    def inspect(self, agent_type: AgentType) -> dict | None:
        agent = self._agents.get(agent_type)
        if agent is None:
            return None
        return {
            "agent_type": str(agent.agent_type),
            "capabilities": list(agent.capabilities),
            "executable": bool(agent.capabilities),
        }

    def list_all(self) -> list[dict]:
        return [self.inspect(t) for t in self._agents]


def build_default_registry() -> AgentRegistry:
    """Register the standard Phase 6 agent set (planner handled by the planner
    subsystem, not as an execution agent)."""

    reg = AgentRegistry()
    for agent in (
        DocumentAgent(),
        ResearchAgent(),
        SpreadsheetAgent(),
        QAAgent(),
        PresentationAgent(),
        CodingAgent(),
        CommunicationAgent(),
        BrowserAutomationAgent(),
        ComputerAutomationAgent(),
    ):
        reg.register(agent)
    return reg
