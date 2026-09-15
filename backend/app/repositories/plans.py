"""Plan + step repository. Plans are immutable versions."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import TaskPlan, TaskStep


async def next_plan_version(session: AsyncSession, task_id: str) -> int:
    res = await session.execute(
        select(func.max(TaskPlan.version)).where(TaskPlan.task_id == task_id)
    )
    current = res.scalar_one_or_none() or 0
    return int(current) + 1


async def add_plan(session: AsyncSession, plan: TaskPlan) -> TaskPlan:
    session.add(plan)
    await session.flush()
    return plan


async def add_step(session: AsyncSession, step: TaskStep) -> TaskStep:
    session.add(step)
    await session.flush()
    return step


async def get_plan(session: AsyncSession, plan_id: str) -> TaskPlan | None:
    return await session.get(TaskPlan, plan_id)


async def get_plan_by_version(
    session: AsyncSession, task_id: str, version: int
) -> TaskPlan | None:
    res = await session.execute(
        select(TaskPlan).where(
            TaskPlan.task_id == task_id, TaskPlan.version == version
        )
    )
    return res.scalar_one_or_none()


async def list_plans(session: AsyncSession, task_id: str) -> Sequence[TaskPlan]:
    res = await session.execute(
        select(TaskPlan).where(TaskPlan.task_id == task_id).order_by(TaskPlan.version)
    )
    return res.scalars().all()


async def get_steps_for_plan(session: AsyncSession, plan_id: str) -> Sequence[TaskStep]:
    res = await session.execute(
        select(TaskStep).where(TaskStep.plan_id == plan_id).order_by(TaskStep.index)
    )
    return res.scalars().all()


async def get_steps_for_task_version(
    session: AsyncSession, task_id: str, plan_version: int
) -> Sequence[TaskStep]:
    plan = await get_plan_by_version(session, task_id, plan_version)
    if plan is None:
        return []
    return await get_steps_for_plan(session, plan.id)


async def get_step(session: AsyncSession, step_id: str) -> TaskStep | None:
    return await session.get(TaskStep, step_id)
