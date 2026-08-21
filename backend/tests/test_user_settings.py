import asyncio
import os
import time
import types
import unittest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("EMBEDDING_API_KEY", "test-key")

from services.user_data_service import UserDataService


class _SettingsQuery:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def upsert(self, *args, **kwargs):
        return self

    def execute(self):
        time.sleep(0.05)
        if self.error:
            raise self.error
        return self.result


class _SettingsDatabase:
    def __init__(self, query):
        self.query = query

    def table(self, name):
        return self.query


class UserSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_settings_read_does_not_block_event_loop(self):
        query = _SettingsQuery(
            types.SimpleNamespace(data=[{"settings": {"darkMode": True}}])
        )
        service = UserDataService.__new__(UserDataService)
        service.client = _SettingsDatabase(query)

        read = asyncio.create_task(service.get_settings("user-1"))
        await asyncio.sleep(0.01)

        self.assertFalse(read.done())
        self.assertEqual({"darkMode": True}, await read)

    async def test_settings_write_failure_is_not_reported_as_success(self):
        service = UserDataService.__new__(UserDataService)
        service.client = _SettingsDatabase(
            _SettingsQuery(error=RuntimeError("database unavailable"))
        )

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await service.save_settings("user-1", {"darkMode": True})


if __name__ == "__main__":
    unittest.main()
