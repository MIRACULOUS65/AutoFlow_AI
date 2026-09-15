"""Agent registry repository (read-only, not workspace-scoped)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent


async def get_agent(session: AsyncSession, agent_id: str) -> Agent | None:
    return await session.get(Agent, agent_id)


async def list_agents(session: AsyncSession) -> Sequence[Agent]:
    res = await session.execute(select(Agent).order_by(Agent.name))
    return res.scalars().all()
