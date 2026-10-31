"""Readiness: can this process reach what it depends on right now?

Supabase is required. The app Postgres and Redis are checked only when configured.
"""
import asyncio
from typing import Dict, Tuple

from config.settings import settings

TIMEOUT = 3.0


async def _supabase() -> str:
    from db.client import async_db, get_supabase_client

    client = get_supabase_client()
    await asyncio.wait_for(
        async_db(lambda: client.table("projects").select("id").limit(1).execute()), TIMEOUT
    )
    return "ok"


async def _vector_db() -> str:
    if not settings.VECTOR_DATABASE_URL:
        return "not configured"
    import asyncpg

    conn = await asyncio.wait_for(asyncpg.connect(settings.VECTOR_DATABASE_URL), TIMEOUT)
    try:
        await conn.fetchval("SELECT 1")
    finally:
        await conn.close()
    return "ok"


async def _redis() -> str:
    if not settings.REDIS_URL:
        return "not configured"
    from redis import asyncio as aioredis

    client = aioredis.from_url(settings.REDIS_URL)
    try:
        await asyncio.wait_for(client.ping(), TIMEOUT)
    finally:
        await client.aclose()
    return "ok"


async def check() -> Tuple[bool, Dict[str, str]]:
    names = ("supabase", "vector_db", "redis")
    results = await asyncio.gather(_supabase(), _vector_db(), _redis(), return_exceptions=True)
    checks = {
        name: (f"error: {type(r).__name__}" if isinstance(r, BaseException) else r)
        for name, r in zip(names, results)
    }
    ready = all(v in ("ok", "not configured") for v in checks.values())
    return ready, checks
