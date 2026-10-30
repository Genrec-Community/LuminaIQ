from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from config.settings import settings
from utils.logger import logger
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor


# Dedicated thread pool for Supabase calls — prevents blocking the event loop
_db_executor = ThreadPoolExecutor(
    max_workers=64,
    thread_name_prefix="supabase_db"
)


class SupabaseClient:
    _instance = None
    _max_retries = 3

    @classmethod
    def get_instance(cls) -> Client:
        if cls._instance is None:
            cls._create_client()
        return cls._instance

    @classmethod
    def _create_client(cls):
        """Create client with retry logic for DNS resolution issues."""
        last_error = None
        for attempt in range(cls._max_retries):
            try:
                options = SyncClientOptions(
                    postgrest_client_timeout=60,
                    storage_client_timeout=60,
                    function_client_timeout=30,
                )
                cls._instance = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_SERVICE_KEY,
                    options=options,
                )
                logger.info("Supabase client connected successfully")
                return
            except Exception as e:
                last_error = e
                if attempt < cls._max_retries - 1:
                    wait = 2 * (attempt + 1)
                    logger.warning(
                        f"Supabase connection attempt {attempt+1} failed ({e}), retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    logger.error(f"Failed to connect to Supabase after {cls._max_retries} attempts: {e}")
                    raise last_error

    @classmethod
    def reset(cls):
        """Reset the client instance (forces reconnection on next call)."""
        cls._instance = None


def get_supabase_client() -> Client:
    """Get the Supabase client instance (lazy, with retry)."""
    return SupabaseClient.get_instance()


# Lazy initialization — don't connect at import time.
supabase_client = None


def _get_lazy_client() -> Client:
    global supabase_client
    if supabase_client is None:
        supabase_client = get_supabase_client()
    return supabase_client


# ============================================================================
# Async DB Wrapper — runs sync Supabase calls in a dedicated thread pool
# so they DON'T block the event loop
# ============================================================================

# Supabase closes idle keep-alive connections; the next request on one fails at
# once with "Server disconnected" before reaching the server. Those are retried.
_TRANSIENT = ("server disconnected", "remoteprotocolerror", "connectionterminated",
              "connection reset", "readerror", "broken pipe", "connection aborted")


def _is_transient(e: Exception) -> bool:
    text = f"{type(e).__name__} {e}".lower()
    return any(t in text for t in _TRANSIENT)


async def _run_with_retry(fn):
    loop = asyncio.get_running_loop()
    for attempt in range(3):
        try:
            return await loop.run_in_executor(_db_executor, fn)
        except Exception as e:
            if attempt == 2 or not _is_transient(e):
                raise
            await asyncio.sleep(0.2 * (attempt + 1))


async def async_db_execute(func, *args, **kwargs):
    """
    Run a synchronous Supabase operation in a dedicated thread pool.

    This prevents sync DB calls from blocking the asyncio event loop,
    which is critical for multi-tenant performance.

    Usage:
        # Instead of (BLOCKS event loop):
        result = client.table("docs").select("*").execute()

        # Use (NON-BLOCKING):
        result = await async_db_execute(
            lambda: client.table("docs").select("*").execute()
        )
    """
    return await _run_with_retry(lambda: func(*args))


async def async_db(callable_fn):
    """
    Shorthand wrapper for async DB execution.

    Usage:
        result = await async_db(
            lambda: client.table("docs").select("*").eq("id", doc_id).execute()
        )
    """
    return await _run_with_retry(callable_fn)
