from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from config.settings import settings
from utils.logger import logger
import time


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
# This prevents DNS failures from crashing the entire app on startup.
supabase_client = None


def _get_lazy_client() -> Client:
    global supabase_client
    if supabase_client is None:
        supabase_client = get_supabase_client()
    return supabase_client
