"""Readiness: can this process reach what it depends on right now?

The database and Supabase (sign-in) are required; Redis is checked only when configured.
"""
import asyncio
from typing import Dict, Tuple

from config.settings import settings

TIMEOUT = 3.0


async def _database() -> str:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    import psycopg

    conn = await asyncio.wait_for(psycopg.AsyncConnection.connect(settings.DATABASE_URL), TIMEOUT)
    async with conn:
        await conn.execute("SELECT 1")
    return "ok"


async def _supabase_auth() -> str:
    import httpx

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(f"{settings.SUPABASE_URL}/auth/v1/health",
                               headers={"apikey": settings.SUPABASE_KEY or settings.SUPABASE_SERVICE_KEY})
    res.raise_for_status()
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
    names = ("database", "supabase_auth", "redis")
    results = await asyncio.gather(_database(), _supabase_auth(), _redis(), return_exceptions=True)
    checks = {
        name: (f"error: {type(r).__name__}" if isinstance(r, BaseException) else r)
        for name, r in zip(names, results)
    }
    ready = all(v in ("ok", "not configured") for v in checks.values())
    return ready, checks
