from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from config.settings import settings

class SupabaseClient:
    _instance = None

    @classmethod
    def get_instance(cls) -> Client:
        if cls._instance is None:
            options = SyncClientOptions(
                postgrest_client_timeout=15,
                storage_client_timeout=15,
                function_client_timeout=10,
            )
            cls._instance = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY,
                options=options,
            )
        return cls._instance

supabase_client = SupabaseClient.get_instance()
