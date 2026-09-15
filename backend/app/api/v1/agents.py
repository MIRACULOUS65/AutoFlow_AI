"""Agent registry endpoints (read-only; no internal reasoning exposed)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbDep, PrincipalDep
from app.core.errors import not_found
from app.repositories import agents as agents_repo
from app.schemas.agents import AgentDetail, AgentSummary, AgentTool

router = APIRouter(prefix="/agents", tags=["agents"])


def _summary(a) -> AgentSummary:
    return AgentSummary(
        id=a.id,
        name=a.name,
        description=a.description,
        capabilities=a.capabilities or [],
        supported_tools=a.supported_tools or [],
        status=a.status,
        version=a.version,
    )


@router.get("", response_model=list[AgentSummary])
async def list_agents(session: DbDep, principal: PrincipalDep) -> list[AgentSummary]:
    return [_summary(a) for a in await agents_repo.list_agents(session)]


@router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(agent_id: str, session: DbDep, principal: PrincipalDep) -> AgentDetail:
    a = await agents_repo.get_agent(session, agent_id)
    if a is None:
        raise not_found("Agent", agent_id)
    return AgentDetail(
        **_summary(a).model_dump(by_alias=True),
        summary=a.summary,
        tools=[AgentTool(**t) if isinstance(t, dict) else AgentTool(id=t, name=t) for t in (a.tools or [])],
    )
