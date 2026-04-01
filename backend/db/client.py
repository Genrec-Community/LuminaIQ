"""
Supabase database client with connection pool management.

Uses a ThreadPoolExecutor as the concurrency pool for synchronous Supabase
calls, with configurable min/max workers, timeout enforcement, and pool
utilization metrics (active, idle, waiting).
"""

import time
import asyncio
import threading
import logging
import httpx
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Callable, Any, Optional

from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions

from config.settings import settings

logger = logging.getLogger(__name__)


@contextmanager
def _null_ctx():
    """No-op context manager used when telemetry is unavailable."""
    yield None


# ---------------------------------------------------------------------------
# Connection Pool
# ---------------------------------------------------------------------------

class _ConnectionPool:
    """
    Thread-pool-backed connection pool for synchronous Supabase calls.

    Tracks active, idle, and waiting counts so callers can monitor
    utilisation and emit warnings when the pool is under pressure.

    Configuration (from settings):
        DB_POOL_MIN_SIZE  – minimum (initial) worker threads  (default 5)
        DB_POOL_MAX_SIZE  – maximum worker threads            (default 20)
        DB_POOL_TIMEOUT   – seconds to wait for a free slot   (default 10)
    """

    # Pool configuration — read from settings with safe fallbacks
    MIN_SIZE: int = getattr(settings, "DB_POOL_MIN_SIZE", 5)
    MAX_SIZE: int = getattr(settings, "DB_POOL_MAX_SIZE", 20)
    TIMEOUT: float = getattr(settings, "DB_POOL_TIMEOUT", 10.0)

    # Warn when utilisation exceeds this fraction
    WARN_THRESHOLD: float = 0.80

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_SIZE,
            thread_name_prefix="supabase_pool",
        )
        self._lock = threading.Lock()
        self._active: int = 0    # tasks currently executing
        self._waiting: int = 0   # tasks queued, waiting for a free slot

    # ------------------------------------------------------------------
    # Public metrics
    # ------------------------------------------------------------------

    @property
    def active(self) -> int:
        return self._active

    @property
    def idle(self) -> int:
        """Approximate idle workers (max_size - active)."""
        return max(0, self.MAX_SIZE - self._active)

    @property
    def waiting(self) -> int:
        return self._waiting

    @property
    def utilization(self) -> float:
        """Fraction of max workers that are currently active (0.0–1.0)."""
        return self._active / self.MAX_SIZE if self.MAX_SIZE > 0 else 0.0

    def get_metrics(self) -> dict:
        return {
            "active": self._active,
            "idle": self.idle,
            "waiting": self._waiting,
            "max_size": self.MAX_SIZE,
            "min_size": self.MIN_SIZE,
            "utilization": round(self.utilization, 4),
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(self, func: Callable, *args: Any) -> Any:
        """
        Submit *func* to the pool and await its result.

        Raises:
            asyncio.TimeoutError: if no slot is available within TIMEOUT seconds.
        """
        loop = asyncio.get_running_loop()

        with self._lock:
            self._waiting += 1

        try:
            future = loop.run_in_executor(self._executor, self._tracked(func), *args)
            return await asyncio.wait_for(future, timeout=self.TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning(
                "Connection pool timeout after %.1fs — pool metrics: %s",
                self.TIMEOUT,
                self.get_metrics(),
            )
            raise
        finally:
            with self._lock:
                self._waiting = max(0, self._waiting - 1)

    def _tracked(self, func: Callable) -> Callable:
        """Wrap *func* to increment/decrement the active counter."""
        pool = self

        def wrapper(*args: Any) -> Any:
            with pool._lock:
                pool._active += 1
            util = pool.utilization
            if util >= pool.WARN_THRESHOLD:
                logger.warning(
                    "Connection pool utilization at %.0f%% (%d/%d active) — "
                    "consider increasing DB_POOL_MAX_SIZE",
                    util * 100,
                    pool._active,
                    pool.MAX_SIZE,
                )
            try:
                return func(*args)
            finally:
                with pool._lock:
                    pool._active = max(0, pool._active - 1)

        return wrapper

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)


# Module-level pool instance
_pool = _ConnectionPool()


def get_pool() -> _ConnectionPool:
    """Return the module-level connection pool (for metrics / testing)."""
    return _pool


# ---------------------------------------------------------------------------
# Supabase singleton client
# ---------------------------------------------------------------------------

class SupabaseClient:
    _instance: Optional[Client] = None
    _max_retries: int = 3

    @classmethod
    def get_instance(cls) -> Client:
        if cls._instance is None:
            cls._create_client()
        return cls._instance  # type: ignore[return-value]

    @classmethod
    def _create_client(cls) -> None:
        """
        Create a single shared client with HTTP/1.1 forced to prevent
        HTTP/2 stream exhaustion on Cloudflare (root cause of all
        'Server disconnected' and '400 Bad Request' errors).
        """
        last_error: Optional[Exception] = None
        for attempt in range(cls._max_retries):
            try:
                http1_client = httpx.Client(
                    transport=httpx.HTTPTransport(http2=False),
                    timeout=60.0,
                )
                options = SyncClientOptions(
                    postgrest_client_timeout=60,
                    storage_client_timeout=60,
                    function_client_timeout=30,
                    httpx_client=http1_client,
                )
                cls._instance = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_SERVICE_KEY,
                    options=options,
                )
                logger.info("Supabase client connected successfully (HTTP/1.1 singleton)")
                return
            except Exception as exc:
                last_error = exc
                if attempt < cls._max_retries - 1:
                    wait = 2 * (attempt + 1)
                    logger.warning(
                        "Supabase connection attempt %d failed (%s), retrying in %ds…",
                        attempt + 1,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "Failed to connect to Supabase after %d attempts: %s",
                        cls._max_retries,
                        exc,
                    )
                    raise last_error  # type: ignore[misc]

    @classmethod
    def reset(cls) -> None:
        """Reset the client instance (forces reconnection on next call)."""
        cls._instance = None


def get_supabase_client() -> Client:
    """Return the shared Supabase singleton."""
    return SupabaseClient.get_instance()


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------

async def async_db_execute(func: Callable, *args: Any) -> Any:
    """
    Run a synchronous Supabase operation through the connection pool.

    Usage::

        result = await async_db_execute(
            lambda: client.table("docs").select("*").execute()
        )
    """
    start_time = time.time()
    success = False
    error_msg: Optional[str] = None

    try:
        from core.telemetry import get_telemetry_service
        telemetry = get_telemetry_service()
    except Exception:
        telemetry = None

    ctx = telemetry.start_span("db.supabase_query", properties={"operation": "query"}) if telemetry else _null_ctx()
    with ctx as span:
        try:
            result = await _pool.run(func, *args)
            success = True
            return result
        except Exception as exc:
            error_msg = str(exc)
            if span:
                try:
                    from opentelemetry.trace import Status, StatusCode
                    span.set_status(Status(StatusCode.ERROR, error_msg))
                    span.record_exception(exc)
                except Exception:
                    pass
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _emit_telemetry(telemetry, duration_ms, success, error_msg, "query")
            _maybe_track_pool_metrics(telemetry)


async def async_db(callable_fn: Callable) -> Any:
    """
    Shorthand wrapper for async DB execution with telemetry tracking.

    Usage::

        result = await async_db(
            lambda: client.table("docs").select("*").eq("id", doc_id).execute()
        )
    """
    start_time = time.time()
    success = False
    error_msg: Optional[str] = None

    try:
        from core.telemetry import get_telemetry_service
        telemetry = get_telemetry_service()
    except Exception:
        telemetry = None

    ctx = telemetry.start_span("db.supabase_query", properties={"operation": "query"}) if telemetry else _null_ctx()
    with ctx as span:
        try:
            result = await _pool.run(callable_fn)
            success = True
            return result
        except Exception as exc:
            error_msg = str(exc)
            if span:
                try:
                    from opentelemetry.trace import Status, StatusCode
                    span.set_status(Status(StatusCode.ERROR, error_msg))
                    span.record_exception(exc)
                except Exception:
                    pass
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            _emit_telemetry(telemetry, duration_ms, success, error_msg, "query")
            _maybe_track_pool_metrics(telemetry)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _emit_telemetry(
    telemetry: Any,
    duration_ms: float,
    success: bool,
    error_msg: Optional[str],
    operation: str,
) -> None:
    """Track a Supabase dependency call in telemetry (best-effort)."""
    try:
        if telemetry:
            props: dict = {"operation": operation}
            if error_msg:
                props["error"] = error_msg
            telemetry.track_dependency(
                name="Supabase query",
                dependency_type="supabase",
                duration=duration_ms,
                success=success,
                properties=props,
            )
    except Exception as err:
        logger.debug("Failed to track telemetry: %s", err)


def _maybe_track_pool_metrics(telemetry: Any) -> None:
    """Emit pool utilisation metric to telemetry (best-effort)."""
    try:
        if telemetry:
            metrics = _pool.get_metrics()
            telemetry.track_metric(
                name="db.pool.utilization",
                value=metrics["utilization"],
                properties={
                    "active": str(metrics["active"]),
                    "idle": str(metrics["idle"]),
                    "waiting": str(metrics["waiting"]),
                    "max_size": str(metrics["max_size"]),
                },
            )
    except Exception as err:
        logger.debug("Failed to track pool metrics: %s", err)
