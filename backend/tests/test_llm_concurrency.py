import asyncio
import types
import unittest

from services.llm_service import LLMService


class _Client:
    def __init__(self):
        self.active = 0
        self.peak = 0

    async def achat(self, messages):
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return types.SimpleNamespace(
            message=types.SimpleNamespace(content="A complete model response."),
            raw=None,
        )


class LLMConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_completions_share_one_concurrency_limit(self):
        client = _Client()
        service = LLMService.__new__(LLMService)
        service._clients = {}
        service._request_semaphore = asyncio.Semaphore(2)
        service._get_client = lambda **kwargs: client

        await asyncio.gather(
            *[
                service.chat_completion([{"role": "user", "content": str(index)}])
                for index in range(10)
            ]
        )

        self.assertEqual(2, client.peak)


if __name__ == "__main__":
    unittest.main()
