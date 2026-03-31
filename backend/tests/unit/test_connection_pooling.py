"""Unit tests for Supabase connection pool (backend/db/client.py)."""

import asyncio
import pytest
from unittest.mock import patch


def _make_pool(max_size=5, timeout=2.0, min_size=1):
    from db.client import _ConnectionPool
    pool = _ConnectionPool.__new__(_ConnectionPool)
    pool.MAX_SIZE = max_size
    pool.MIN_SIZE = min_size
    pool.TIMEOUT = timeout
    pool.WARN_THRESHOLD = 0.80
    _ConnectionPool.__init__(pool)
    return pool


# --- metrics ---

def test_initial_metrics():
    pool = _make_pool(max_size=10)
    m = pool.get_metrics()
    assert m["active"] == 0
    assert m["waiting"] == 0
    assert m["idle"] == 10
    assert m["max_size"] == 10
    assert m["utilization"] == 0.0


@pytest.mark.asyncio
async def test_active_count_increments_during_execution():
    pool = _make_pool(max_size=4)
    observed = []

    def task():
        observed.append(pool.active)
        return "done"

    await pool.run(task)
    assert observed == [1]
    assert pool.active == 0


@pytest.mark.asyncio
async def test_active_returns_to_zero_after_completion():
    pool = _make_pool(max_size=4)
    await pool.run(lambda: "result")
    assert pool.active == 0
    assert pool.idle == 4


@pytest.mark.asyncio
async def test_sequential_tasks_never_exceed_max():
    pool = _make_pool(max_size=3)
    for _ in range(10):
        await pool.run(lambda: None)
        assert pool.active <= pool.MAX_SIZE


# --- exhaustion / timeout ---

@pytest.mark.asyncio
async def test_pool_timeout_raises():
    """Pool raises asyncio.TimeoutError when TIMEOUT is exceeded."""
    pool = _make_pool(max_size=1, timeout=0.1)
    original = asyncio.wait_for
    calls = [0]

    async def mock_wait_for(fut, timeout):
        calls[0] += 1
        if calls[0] == 1:
            return await original(fut, timeout=5.0)
        # Cancel the future instead of calling .close() (Future has no close())
        if hasattr(fut, "cancel"):
            fut.cancel()
        raise asyncio.TimeoutError()

    with patch("asyncio.wait_for", side_effect=mock_wait_for):
        await pool.run(lambda: "first")
        with pytest.raises(asyncio.TimeoutError):
            await pool.run(lambda: "second")


@pytest.mark.asyncio
async def test_waiting_counter_resets_after_task():
    pool = _make_pool(max_size=4)
    await pool.run(lambda: "task")
    assert pool.waiting == 0


# --- utilisation warning ---

@pytest.mark.asyncio
async def test_utilisation_warning_logged(caplog):
    import logging
    pool = _make_pool(max_size=1, timeout=2.0)
    with caplog.at_level(logging.WARNING):
        await pool.run(lambda: None)
    msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("utilization" in m.lower() or "pool" in m.lower() for m in msgs)


def test_utilisation_calculation():
    pool = _make_pool(max_size=20)
    pool._active = 10
    assert pool.utilization == pytest.approx(0.5)
    pool._active = 16
    assert pool.utilization == pytest.approx(0.8)
    pool._active = 20
    assert pool.utilization == pytest.approx(1.0)


# --- async_db wrappers ---

@pytest.mark.asyncio
async def test_async_db_returns_result():
    from db.client import async_db

    async def _run(fn):
        return fn()

    with patch("db.client._pool") as mp:
        mp.run.side_effect = _run
        mp.get_metrics.return_value = {"active": 0, "idle": 20, "waiting": 0, "max_size": 20, "utilization": 0.0}
        result = await async_db(lambda: {"data": [{"id": "doc1"}]})
        assert result == {"data": [{"id": "doc1"}]}


@pytest.mark.asyncio
async def test_async_db_propagates_exception():
    from db.client import async_db

    async def _run(fn):
        return fn()

    with patch("db.client._pool") as mp:
        mp.run.side_effect = _run
        mp.get_metrics.return_value = {"active": 0, "idle": 20, "waiting": 0, "max_size": 20, "utilization": 0.0}
        with pytest.raises(RuntimeError, match="DB error"):
            await async_db(lambda: (_ for _ in ()).throw(RuntimeError("DB error")))


@pytest.mark.asyncio
async def test_async_db_execute_returns_result():
    from db.client import async_db_execute

    async def _run(fn, *args):
        return fn(*args)

    with patch("db.client._pool") as mp:
        mp.run.side_effect = _run
        mp.get_metrics.return_value = {"active": 0, "idle": 20, "waiting": 0, "max_size": 20, "utilization": 0.0}
        result = await async_db_execute(lambda: "executed")
        assert result == "executed"


# --- configuration ---

def test_pool_min_max_size():
    pool = _make_pool(min_size=5, max_size=20)
    assert pool.MIN_SIZE == 5
    assert pool.MAX_SIZE == 20


def test_pool_timeout_config():
    pool = _make_pool(timeout=10.0)
    assert pool.TIMEOUT == 10.0


def test_get_pool_returns_module_pool():
    from db.client import get_pool, _pool
    assert get_pool() is _pool
