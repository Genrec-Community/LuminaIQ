from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from config.settings import settings
from utils.logger import logger
import time
import asyncio
import httpx
from concurrent.futures import ThreadPoolExecutor


# Dedicated thread pool for Supabase calls — prevents blocking the event loop
_db_executor = ThreadPoolExecutor(
    max_workers=8,
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
        """Create a single shared client with HTTP/1.1 forced to prevent
        HTTP/2 stream exhaustion on Cloudflare (root cause of all
        'Server disconnected' and '400 Bad Request' errors)."""
        last_error = None
        for attempt in range(cls._max_retries):
            try:
                # Force HTTP/1.1: prevents Cloudflare from multiplexing too
                # many concurrent requests over a single HTTP/2 connection,
                # which causes ConnectionTerminated and 400 errors under load.
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
    """Get the shared Supabase singleton. Always returns the same instance."""
    return SupabaseClient.get_instance()


# ============================================================================
# Async DB Wrapper — runs sync Supabase calls in a dedicated thread pool
# so they DON'T block the event loop
# ============================================================================

async def async_db_execute(func, *args, **kwargs):
    """
    Run a synchronous Supabase operation in a dedicated thread pool.

    Usage:
        result = await async_db_execute(
            lambda: client.table("docs").select("*").execute()
        )
    """
    start_time = time.time()
    success = False
    error_msg = None
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(_db_executor, func, *args)
        success = True
        return result
    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        
        # Track telemetry
        try:
            from core.telemetry import get_telemetry_service
            telemetry = get_telemetry_service()
            
            properties = {
                "operation": "query",
            }
            if error_msg:
                properties["error"] = error_msg
            
            telemetry.track_dependency(
                name=f"Supabase query",
                dependency_type="supabase",
                duration=duration_ms,
                success=success,
                properties=properties
            )
        except Exception as telemetry_err:
            logger.debug(f"Failed to track telemetry: {telemetry_err}")


async def async_db(callable_fn):
    """
    Shorthand wrapper for async DB execution with telemetry tracking.

    Usage:
        result = await async_db(
            lambda: client.table("docs").select("*").eq("id", doc_id).execute()
        )
    """
    start_time = time.time()
    success = False
    error_msg = None
    
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(_db_executor, callable_fn)
        success = True
        return result
    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        
        # Track telemetry
        try:
            from core.telemetry import get_telemetry_service
            telemetry = get_telemetry_service()
            
            properties = {
                "operation": "query",
            }
            if error_msg:
                properties["error"] = error_msg
            
            telemetry.track_dependency(
                name=f"Supabase query",
                dependency_type="supabase",
                duration=duration_ms,
                success=success,
                properties=properties
            )
        except Exception as telemetry_err:
            logger.debug(f"Failed to track telemetry: {telemetry_err}")
