"""
Shared cache for every web and worker process.

Redis when REDIS_URL is set; otherwise the cache_entries table in Postgres;
memory only when neither is configured (tests, scripts). A short in-process
layer (L1, a few seconds) absorbs repeated reads of hot keys. Values must be
JSON-serialisable.

    from utils.cache import get_cache
    cache = get_cache()
    await cache.set("summary:abc", {...}, ttl=3600)
    await cache.get("summary:abc")
"""

import asyncio
import json
import time
from typing import Any, Dict, Optional, Tuple

from utils.logger import logger


class MemoryBackend:
    def __init__(self):
        self._data: Dict[str, Tuple[float, Any]] = {}

    async def get(self, key: str) -> Optional[Any]:
        item = self._data.get(key)
        if not item:
            return None
        if item[0] < time.time():
            self._data.pop(key, None)
            return None
        return item[1]

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self._data[key] = (time.time() + ttl, value)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def clear_prefix(self, prefix: str) -> int:
        keys = [k for k in self._data if k.startswith(prefix)]
        for k in keys:
            del self._data[k]
        return len(keys)


class PostgresBackend:
    def __init__(self, pg):
        self.pg = pg

    async def _sql(self, query: str, params=()):
        return await asyncio.to_thread(self.pg.fetch, query, params)

    async def get(self, key: str) -> Optional[Any]:
        rows = await self._sql("SELECT value FROM cache_entries WHERE key = %s AND expires_at > now()", (key,))
        return rows[0]["value"] if rows else None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        await self._sql(
            """INSERT INTO cache_entries (key, value, expires_at)
               VALUES (%s, %s::jsonb, now() + make_interval(secs => %s))
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, expires_at = EXCLUDED.expires_at""",
            (key, json.dumps(value), ttl))

    async def delete(self, key: str) -> None:
        await self._sql("DELETE FROM cache_entries WHERE key = %s", (key,))

    async def clear_prefix(self, prefix: str) -> int:
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = await self._sql("DELETE FROM cache_entries WHERE key LIKE %s ESCAPE '\\' RETURNING key",
                               (escaped + "%",))
        return len(rows)

    async def purge_expired(self) -> int:
        rows = await self._sql("DELETE FROM cache_entries WHERE expires_at <= now() RETURNING key")
        return len(rows)


class RedisBackend:
    def __init__(self, url: str):
        from redis import asyncio as aioredis
        self.r = aioredis.from_url(url)

    async def get(self, key: str) -> Optional[Any]:
        raw = await self.r.get(key)
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        await self.r.set(key, json.dumps(value), ex=max(1, int(ttl)))

    async def delete(self, key: str) -> None:
        await self.r.delete(key)

    async def clear_prefix(self, prefix: str) -> int:
        n = 0
        async for k in self.r.scan_iter(match=prefix.replace("*", "\\*").replace("?", "\\?") + "*"):
            n += await self.r.delete(k)
        return n


class Cache:
    def __init__(self, backend, l1_seconds: float = 5.0):
        self.backend = backend
        self.l1_seconds = l1_seconds
        self._l1: Dict[str, Tuple[float, Any]] = {}

    def _l1_put(self, key: str, value: Any, ttl: float) -> None:
        if self.l1_seconds > 0:
            self._l1[key] = (time.monotonic() + min(self.l1_seconds, ttl), value)
            if len(self._l1) > 5000:   # keep the local layer small
                self._l1.clear()

    async def get(self, key: str) -> Optional[Any]:
        item = self._l1.get(key)
        if item and item[0] > time.monotonic():
            return item[1]
        try:
            value = await self.backend.get(key)
        except Exception as e:   # a cache outage must never break a request
            logger.warning(f"[Cache] get failed: {e}")
            return None
        if value is not None:
            self._l1_put(key, value, self.l1_seconds)
        return value

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._l1_put(key, value, ttl)
        try:
            await self.backend.set(key, value, ttl)
        except Exception as e:
            logger.warning(f"[Cache] set failed: {e}")

    async def delete(self, key: str) -> None:
        self._l1.pop(key, None)
        try:
            await self.backend.delete(key)
        except Exception as e:
            logger.warning(f"[Cache] delete failed: {e}")

    async def clear_prefix(self, prefix: str) -> int:
        for k in [k for k in self._l1 if k.startswith(prefix)]:
            del self._l1[k]
        try:
            return await self.backend.clear_prefix(prefix)
        except Exception as e:
            logger.warning(f"[Cache] clear_prefix failed: {e}")
            return 0


_cache: Optional[Cache] = None


def get_cache() -> Cache:
    """The process-wide cache, on the best backend configured."""
    global _cache
    if _cache is None:
        from config.settings import settings
        if settings.REDIS_URL:
            _cache = Cache(RedisBackend(settings.REDIS_URL))
        elif settings.DATABASE_URL:
            from db.client import get_supabase_client
            _cache = Cache(PostgresBackend(get_supabase_client().pg))
        else:
            _cache = Cache(MemoryBackend())
    return _cache
