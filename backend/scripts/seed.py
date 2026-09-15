"""Seed entrypoint:  python -m scripts.seed  [--force]"""

from __future__ import annotations

import asyncio
import sys

from app.core.logging import configure_logging
from app.db.seed import seed
from app.db.session import create_all, dispose_engine


async def main() -> None:
    configure_logging()
    force = "--force" in sys.argv
    await create_all()
    result = await seed(force=force)
    print(result)
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
