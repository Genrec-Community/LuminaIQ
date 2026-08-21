import asyncio
import os
import time
import types
import unittest

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("EMBEDDING_API_KEY", "test-key")

from services.auth_service import AuthService


class _BlockingAuth:
    def get_user(self, token):
        time.sleep(0.1)
        return types.SimpleNamespace(
            user=types.SimpleNamespace(
                id="user-1",
                email="user@example.com",
                user_metadata={"full_name": "User One"},
            )
        )


class AuthResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_token_exchange_does_not_block_event_loop(self):
        service = AuthService.__new__(AuthService)
        service.client = types.SimpleNamespace(auth=_BlockingAuth())

        exchange = asyncio.create_task(service.exchange_supabase_token("token"))
        await asyncio.sleep(0.02)

        self.assertFalse(exchange.done())
        result = await exchange
        self.assertEqual("user-1", result["user"]["id"])


if __name__ == "__main__":
    unittest.main()
