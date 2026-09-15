"""Standalone worker entrypoint.

Run separately in production:

    python -m app.workers.task_worker

In development the API can run an inline worker (RUN_INLINE_WORKER=true).
"""

from __future__ import annotations

import asyncio

from app.core.logging import configure_logging
from app.db.session import create_all, dispose_engine
from app.workers.execution_worker import run_worker


async def main() -> None:
    configure_logging()
    await create_all()
    try:
        await run_worker()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
