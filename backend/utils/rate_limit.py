"""
Per-user rate limits for the expensive endpoints (AI calls, uploads).

Fixed windows counted in Redis when REDIS_URL is set, else in Postgres
(rate_limit_counters), else in memory, so every process shares the count.
This guards against floods and runaway clients; plan quotas are separate
(services/usage_service.py). If the counter store fails, requests go through.

    @router.post("/stream", dependencies=[Depends(rate_limit("chat"))])
"""

import asyncio
import time
from typing import Dict, Optional, Tuple

from fastapi import Depends, HTTPException

from api.deps import get_current_user
from config.settings import settings
from utils.logger import logger

# bucket -> (setting holding the limit, window in seconds)
BUCKETS: Dict[str, Tuple[str, int]] = {
    "chat": ("RATE_LIMIT_CHAT_PER_MIN", 60),
    "generate": ("RATE_LIMIT_GENERATE_PER_MIN", 60),
    "upload": ("RATE_LIMIT_UPLOAD_PER_HOUR", 3600),
}

MESSAGES = {
    "chat": "You're sending messages too fast. Take a breath and try again in a moment.",
    "generate": "Too many requests in a short time. Please wait a moment and try again.",
    "upload": "Too many uploads in the last hour. Please try again later.",
}


def _window_start(window: int, now: Optional[float] = None) -> int:
    now = time.time() if now is None else now
    return int(now // window * window)


class MemoryCounter:
    def __init__(self):
        self._counts: Dict[str, int] = {}

    async def hit(self, key: str, window: int) -> int:
        start = _window_start(window)
        k = f"{key}:{start}"
        self._counts[k] = self._counts.get(k, 0) + 1
        if len(self._counts) > 50_000:
            self._counts = {k: v for k, v in self._counts.items() if k.endswith(f":{start}")}
        return self._counts[k]


class PostgresCounter:
    def __init__(self, pg):
        self.pg = pg

    async def hit(self, key: str, window: int) -> int:
        rows = await asyncio.to_thread(
            self.pg.fetch,
            """INSERT INTO rate_limit_counters (key, window_start, count) VALUES (%s, to_timestamp(%s), 1)
               ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limit_counters.count + 1
               RETURNING count""",
            (key, _window_start(window)))
        return rows[0]["count"]


class RedisCounter:
    def __init__(self, url: str):
        from redis import asyncio as aioredis
        self.r = aioredis.from_url(url)

    async def hit(self, key: str, window: int) -> int:
        k = f"rl:{key}:{_window_start(window)}"
        async with self.r.pipeline(transaction=True) as p:
            p.incr(k)
            p.expire(k, window + 5)
            count, _ = await p.execute()
        return int(count)


_counter = None


def _get_counter():
    global _counter
    if _counter is None:
        if settings.REDIS_URL:
            _counter = RedisCounter(settings.REDIS_URL)
        elif settings.DATABASE_URL:
            from db.client import get_supabase_client
            _counter = PostgresCounter(get_supabase_client().pg)
        else:
            _counter = MemoryCounter()
    return _counter


def rate_limit(bucket: str):
    setting, window = BUCKETS[bucket]

    async def rate_limit_dependency(current_user: dict = Depends(get_current_user)) -> None:
        if not settings.RATE_LIMITS_ENABLED:
            return
        limit = int(getattr(settings, setting))
        try:
            count = await _get_counter().hit(f"{bucket}:{current_user['id']}", window)
        except Exception as e:
            logger.warning(f"[RateLimit] counter unavailable, allowing request: {e}")
            return
        if count > limit:
            retry = max(1, _window_start(window) + window - int(time.time()))
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "message": MESSAGES[bucket], "retry_after": retry},
                headers={"Retry-After": str(retry)},
            )

    rate_limit_dependency.__qualname__ = f"rate_limit.{bucket}"
    return rate_limit_dependency
