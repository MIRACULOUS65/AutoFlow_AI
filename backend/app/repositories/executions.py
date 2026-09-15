"""Execution repository + optimistic-concurrency update + event sequencing."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import conflict
from app.models.execution import Execution, ExecutionContextSnapshotModel


async def add_execution(session: AsyncSession, execution: Execution) -> Execution:
    session.add(execution)
    await session.flush()
    return execution


async def get_execution(
    session: AsyncSession,
    execution_id: str,
    *,
    organization_id: str | None = None,
    workspace_id: str | None = None,
) -> Execution | None:
    ex = await session.get(Execution, execution_id)
    if ex is None:
        return None
    if organization_id is not None and ex.organization_id != organization_id:
        return None
    if workspace_id is not None and ex.workspace_id != workspace_id:
        return None
    return ex


async def list_executions(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str | None = None,
    status: str | None = None,
    task_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[Execution], int]:
    base = select(Execution).where(Execution.organization_id == organization_id)
    if workspace_id:
        base = base.where(Execution.workspace_id == workspace_id)
    if status:
        base = base.where(Execution.status == status)
    if task_id:
        base = base.where(Execution.task_id == task_id)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = base.order_by(Execution.created_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return rows, int(total)


async def add_context_snapshot(
    session: AsyncSession, snapshot: ExecutionContextSnapshotModel
) -> ExecutionContextSnapshotModel:
    session.add(snapshot)
    await session.flush()
    return snapshot


async def get_context_snapshot(
    session: AsyncSession, execution_id: str
) -> ExecutionContextSnapshotModel | None:
    res = await session.execute(
        select(ExecutionContextSnapshotModel).where(
            ExecutionContextSnapshotModel.execution_id == execution_id
        )
    )
    return res.scalar_one_or_none()


async def compare_and_swap_version(
    session: AsyncSession, execution: Execution, expected_version: int
) -> None:
    """Optimistic concurrency guard (PRD §51).

    Only advances if execution.version still equals expected_version. Raises a
    CONFLICT AppError if another worker modified the row.
    """
    result = await session.execute(
        update(Execution)
        .where(Execution.id == execution.id, Execution.version == expected_version)
        .values(version=expected_version + 1)
    )
    if result.rowcount == 0:
        raise conflict(
            "Execution was modified concurrently.",
            details={"execution_id": execution.id, "expected_version": expected_version},
        )
    execution.version = expected_version + 1


async def allocate_event_sequence(session: AsyncSession, execution_id: str) -> int:
    """Atomically increment and return the next event sequence for an execution.

    Uses a single UPDATE ... SET last_sequence = last_sequence + 1 which is atomic
    at the row level, then reads back the value. This gives a monotonic sequence
    without relying on arrival time (PRD §19, §27).
    """
    await session.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(last_sequence=Execution.last_sequence + 1)
    )
    res = await session.execute(
        select(Execution.last_sequence).where(Execution.id == execution_id)
    )
    seq = res.scalar_one()
    return int(seq)


async def find_stale_running(session: AsyncSession) -> Sequence[Execution]:
    """Executions that look active but may need a worker (recovery on restart)."""
    res = await session.execute(
        select(Execution).where(
            or_(
                Execution.status == "QUEUED",
                Execution.status == "PLANNING",
                Execution.status == "RUNNING",
                Execution.status == "RECOVERY",
            )
        )
    )
    return res.scalars().all()
