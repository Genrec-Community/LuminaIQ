"""
Background worker process: runs queued jobs (book processing, imports, re-indexing).

    uv run worker.py

Run as many as you like, on any machines; each job runs once. The web process
can also run one inline (WORKER_INLINE=true, the default), so this is only
needed when web and workers scale separately.
"""

import asyncio
import signal

from config.settings import settings


async def main() -> None:
    from db.client import get_supabase_client
    from db.migrate import migrate
    from utils.logger import logger
    from utils.worker import Worker
    import services.jobs  # noqa: F401  (registers the handlers)

    settings.validate_production()
    if settings.RUN_MIGRATIONS:
        await asyncio.to_thread(migrate)

    worker = Worker(get_supabase_client().pg, concurrency=settings.WORKER_CONCURRENCY,
                    poll_seconds=settings.JOB_POLL_SECONDS, stale_seconds=settings.JOB_STALE_SECONDS)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(worker.stop()))
    logger.info("[Worker] waiting for jobs")
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
