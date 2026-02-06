from supabase import create_client, Client
from config.settings import settings

class SupabaseClient:
    _instance = None

    @classmethod
    def get_instance(cls) -> Client:
        if cls._instance is None:
            cls._instance = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY
            )
        return cls._instance

supabase_client = SupabaseClient.get_instance()
