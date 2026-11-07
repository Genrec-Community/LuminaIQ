"""The worker loop runs handlers, completes or retries jobs, and stops cleanly."""

import asyncio

import pytest

from utils import job_queue as q
from utils import worker as w


@pytest.fixture
def pg(pg_client):
    with pg_client.pool.connection() as conn:
        conn.execute("TRUNCATE jobs")
    return pg_client


async def _wait_for(pg, job_id, statuses, timeout=10.0):
    end = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < end:
        job = await asyncio.to_thread(q.get, pg, job_id)
        if job["status"] in statuses:
            return job
        await asyncio.sleep(0.05)
    raise AssertionError(f"job stayed {job['status']}")


def _run(pg, coro_fn, kinds):
    async def main():
        worker = w.Worker(pg, kinds=kinds, concurrency=2, poll_seconds=0.05, heartbeat_seconds=0.1)
        task = asyncio.create_task(worker.run_forever())
        try:
            return await coro_fn(worker)
        finally:
            await worker.stop()
            await task
    return asyncio.run(main())


def test_worker_runs_handler_and_completes(pg, monkeypatch):
    seen = []

    async def ok(job):
        seen.append(job["payload"]["n"])
        return {"double": job["payload"]["n"] * 2}

    monkeypatch.setitem(w.HANDLERS, "t_ok", ok)

    async def scenario(worker):
        job = await asyncio.to_thread(q.enqueue, pg, "t_ok", {"n": 21})
        done = await _wait_for(pg, job["id"], {"done"})
        assert done["result"] == {"double": 42}

    _run(pg, scenario, ["t_ok"])
    assert seen == [21]


def test_worker_retries_failed_handler(pg, monkeypatch):
    calls = {"n": 0}

    async def flaky(job):
        calls["n"] += 1
        raise RuntimeError("temporary")

    monkeypatch.setitem(w.HANDLERS, "t_flaky", flaky)

    async def scenario(worker):
        job = await asyncio.to_thread(q.enqueue, pg, "t_flaky", {}, max_attempts=1)
        failed = await _wait_for(pg, job["id"], {"failed"})
        assert "temporary" in failed["error"]

    _run(pg, scenario, ["t_flaky"])
    assert calls["n"] == 1


def test_unknown_kind_fails_job(pg):
    async def scenario(worker):
        job = await asyncio.to_thread(q.enqueue, pg, "t_nobody", {}, max_attempts=1)
        failed = await _wait_for(pg, job["id"], {"failed"})
        assert "no handler" in failed["error"].lower()

    _run(pg, scenario, ["t_nobody"])


def test_stop_waits_for_running_job(pg, monkeypatch):
    async def slow(job):
        await asyncio.sleep(0.3)
        return "finished"

    monkeypatch.setitem(w.HANDLERS, "t_slow", slow)

    async def scenario(worker):
        job = await asyncio.to_thread(q.enqueue, pg, "t_slow", {})
        await _wait_for(pg, job["id"], {"running"})
        await worker.stop()
        return job

    job = _run(pg, scenario, ["t_slow"])
    assert q.get(pg, job["id"])["status"] == "done"


def test_heartbeats_keep_long_job_from_being_reclaimed(pg, monkeypatch):
    async def long(job):
        await asyncio.sleep(0.6)
        return None

    monkeypatch.setitem(w.HANDLERS, "t_long", long)

    async def scenario(worker):
        job = await asyncio.to_thread(q.enqueue, pg, "t_long", {})
        await _wait_for(pg, job["id"], {"running"})
        await asyncio.sleep(0.4)
        assert await asyncio.to_thread(q.reclaim_stale, pg, 0.3) == 0
        await _wait_for(pg, job["id"], {"done"})

    _run(pg, scenario, ["t_long"])
