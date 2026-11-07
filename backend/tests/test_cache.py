"""Shared cache: same API on Redis, Postgres or memory; shared across processes."""

import asyncio
import os
import time

import pytest

from utils.cache import Cache, MemoryBackend, PostgresBackend


def run(c):
    return asyncio.run(c)


async def _basic(cache):
    await cache.set("a:1", {"x": [1, 2]}, ttl=60)
    assert await cache.get("a:1") == {"x": [1, 2]}
    assert await cache.get("missing") is None
    await cache.set("a:2", "two", ttl=60)
    await cache.set("b:1", 3, ttl=60)
    assert await cache.clear_prefix("a:") >= 2
    assert await cache.get("a:2") is None and await cache.get("b:1") == 3
    await cache.delete("b:1")
    assert await cache.get("b:1") is None


def test_memory_backend_basics():
    run(_basic(Cache(MemoryBackend(), l1_seconds=0)))


def test_memory_backend_expiry():
    async def go():
        cache = Cache(MemoryBackend(), l1_seconds=0)
        await cache.set("k", 1, ttl=1)
        assert await cache.get("k") == 1
        await asyncio.sleep(1.1)
        assert await cache.get("k") is None
    run(go())


def test_postgres_backend_basics_and_sharing(pg_client):
    async def go():
        one = Cache(PostgresBackend(pg_client), l1_seconds=0)
        two = Cache(PostgresBackend(pg_client), l1_seconds=0)   # another "process"
        await _basic(one)
        await one.set("shared", {"v": 1}, ttl=60)
        assert await two.get("shared") == {"v": 1}
        await one.set("short", 1, ttl=1)
        await asyncio.sleep(1.1)
        assert await two.get("short") is None
    run(go())


def test_l1_serves_repeat_reads_without_backend():
    class Counting(MemoryBackend):
        reads = 0

        async def get(self, key):
            Counting.reads += 1
            return await super().get(key)

    async def go():
        cache = Cache(Counting(), l1_seconds=5)
        await cache.set("k", "v", ttl=60)
        for _ in range(5):
            assert await cache.get("k") == "v"
        assert Counting.reads == 0      # set() filled the local layer
    run(go())


def test_prefix_is_literal_not_a_pattern(pg_client):
    async def go():
        cache = Cache(PostgresBackend(pg_client), l1_seconds=0)
        await cache.set("p_%x", 1, ttl=60)
        await cache.set("pAx", 2, ttl=60)
        await cache.clear_prefix("p_%")
        assert await cache.get("pAx") == 2
    run(go())


@pytest.mark.skipif(not os.environ.get("TEST_REDIS_URL"), reason="TEST_REDIS_URL not set")
def test_redis_backend_basics():
    from utils.cache import RedisBackend
    run(_basic(Cache(RedisBackend(os.environ["TEST_REDIS_URL"]), l1_seconds=0)))
