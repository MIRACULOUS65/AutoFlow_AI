"""Execution worker.

Consumes jobs from the queue and advances durably-persisted executions. Each job
runs in its own transactional session. Jobs are idempotent: they load current
state and act on it, so redelivery or a restart continues safely rather than
replaying committed side effects.
"""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.execution import Execution
from app.models.task import Task
from app.services import execution_service, planning_service
from app.workers.queue import get_queue

log = get_logger("worker")


async def handle_job(job: dict) -> None:
    job_type = job.get("job_type")
    task_id = job.get("task_id")
    execution_id = job.get("execution_id")
    if not task_id or not execution_id:
        return

    async with session_scope() as session:
        task = await session.get(Task, task_id)
        execution = await session.get(Execution, execution_id)
        if task is None or execution is None:
            log.warning("job.missing_entities", task_id=task_id, execution_id=execution_id)
            return

        log.info(
            "job.start",
            job_type=job_type,
            task_id=task_id,
            execution_id=execution_id,
            status=execution.status,
        )

        if job_type == "plan_task":
            await planning_service.run_planning(session, task, execution)
            # If planning ended in RUNNING, continue straight into execution.
            if execution.status in ("RUNNING", "RECOVERY"):
                await execution_service.advance(session, task, execution)
        elif job_type in ("resume_execution", "execute_task"):
            await execution_service.advance(session, task, execution)
        else:
            log.warning("job.unknown_type", job_type=job_type)


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    """Long-running consumer loop."""
    queue = get_queue()
    log.info("worker.started")
    while stop_event is None or not stop_event.is_set():
        job = await queue.dequeue(timeout=1.0)
        if job is None:
            continue
        try:
            await handle_job(job)
        except Exception as exc:  # noqa: BLE001 — worker must not die on one job
            log.error("job.error", error=str(exc), job=job)
    log.info("worker.stopped")
