"""
The background worker: claims jobs from the Postgres queue and runs their handlers.

Runs as its own process (`uv run worker.py`) or inside the web process when
WORKER_INLINE=true, so a single `uv run run.py` still does everything. Many
workers on many machines can run at once; each job runs once (see job_queue).

Handlers are `async def handler(job: dict) -> result` registered with
@handler("kind") (see services/jobs.py). A handler that raises makes the job
retry with backoff; the result must be JSON-serialisable.
"""

import asyncio
import os
import socket
import uuid
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional, Set

from utils import job_queue as q
from utils.logger import logger

HANDLERS: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}

HOST = socket.gethostname()


def handler(kind: str):
    def register(fn):
        HANDLERS[kind] = fn
        return fn
    return register


class Worker:
    def __init__(self, pg, *, kinds: Optional[Iterable[str]] = None, concurrency: int = 2,
                 poll_seconds: float = 1.0, heartbeat_seconds: float = 15.0,
                 stale_seconds: float = 300.0):
        self.pg = pg
        self._kinds = list(kinds) if kinds else None   # None = every registered kind
        self.concurrency = max(1, concurrency)
        self.poll_seconds = poll_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.stale_seconds = stale_seconds
        self.worker_id = f"{HOST}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self._running: Set[asyncio.Task] = set()
        self._stopping = asyncio.Event()
        self._stopped = asyncio.Event()

    @property
    def kinds(self):
        return self._kinds or sorted(HANDLERS)

    async def run_forever(self) -> None:
        logger.info(f"[Worker] {self.worker_id} started (concurrency {self.concurrency}, kinds {self.kinds})")
        last_reclaim = 0.0
        loop = asyncio.get_running_loop()
        try:
            while not self._stopping.is_set():
                now = loop.time()
                if now - last_reclaim >= max(self.stale_seconds / 4, 1.0):
                    last_reclaim = now
                    await self._safe(q.reclaim_stale, self.pg, self.stale_seconds)

                job = None
                if len(self._running) < self.concurrency and self.kinds:
                    job = await self._safe(q.claim, self.pg, self.worker_id, HOST, self.kinds)
                if job:
                    task = asyncio.create_task(self._run(job))
                    self._running.add(task)
                    task.add_done_callback(self._running.discard)
                    continue   # look for more work straight away
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_seconds)
                except asyncio.TimeoutError:
                    pass
            if self._running:
                await asyncio.gather(*self._running, return_exceptions=True)
        finally:
            self._stopped.set()
            logger.info(f"[Worker] {self.worker_id} stopped")

    async def stop(self) -> None:
        """Stop claiming new jobs and wait for the running ones to finish."""
        self._stopping.set()
        await self._stopped.wait()

    async def _safe(self, fn, *args):
        try:
            return await asyncio.to_thread(fn, *args)
        except Exception as e:   # database hiccup: try again on the next tick
            logger.warning(f"[Worker] queue call {fn.__name__} failed: {e}")
            return None

    async def _heartbeat(self, job_id: str) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            await self._safe(q.heartbeat, self.pg, job_id, self.worker_id)

    async def _run(self, job: Dict[str, Any]) -> None:
        beat = asyncio.create_task(self._heartbeat(job["id"]))
        try:
            fn = HANDLERS.get(job["kind"])
            if fn is None:
                raise RuntimeError(f"No handler for job kind '{job['kind']}'")
            result = await fn(job)
            await self._safe(q.complete, self.pg, job["id"], result)
        except Exception as e:
            logger.error(f"[Worker] job {job['id']} ({job['kind']}) failed, attempt {job['attempts']}: {e}")
            await self._safe(q.fail, self.pg, job["id"], f"{type(e).__name__}: {e}")
        finally:
            beat.cancel()
