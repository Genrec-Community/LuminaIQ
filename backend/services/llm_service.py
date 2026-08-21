"""Application-scoped LlamaIndex LLM clients for Azure/OpenAI-compatible chat."""

import asyncio
import time
from typing import Dict, List, Tuple

from config.settings import settings
from llama_index.core.llms import ChatMessage, MessageRole
from utils.logger import logger


def _active_model() -> str:
    if settings.AZURE_OPENAI_ENDPOINT:
        return settings.AZURE_OPENAI_MODEL or settings.AZURE_OPENAI_DEPLOYMENT
    return settings.LLM_MODEL or "gpt-4.1-mini"


def _temperature_for_model(requested: float) -> float:
    model = _active_model().lower()
    return 1.0 if "gpt-5" in model or model.startswith("o1") else requested


def _convert_messages(messages: List[Dict[str, str]]) -> List[ChatMessage]:
    roles = {
        "system": MessageRole.SYSTEM,
        "assistant": MessageRole.ASSISTANT,
        "user": MessageRole.USER,
    }
    return [
        ChatMessage(
            role=roles.get(message.get("role", "user"), MessageRole.USER),
            content=message.get("content", ""),
        )
        for message in messages
    ]


def _response_details(response) -> Tuple[str, str, int]:
    answer = response.message.content or ""
    raw = getattr(response, "raw", None)
    finish_reason = ""
    reasoning_tokens = 0
    try:
        finish_reason = raw.choices[0].finish_reason or ""
        details = getattr(raw.usage, "completion_tokens_details", None)
        reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0
    except (AttributeError, IndexError, TypeError):
        pass
    return answer, finish_reason, reasoning_tokens


class LLMService:
    EMPTY_RESPONSE_MIN_CHARS = 20
    RETRY_TOKEN_MULTIPLIER = 3

    def __init__(self):
        self._clients = {}
        self._request_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_LLM)
        provider = "Azure OpenAI" if self._using_azure else "OpenAI-compatible"
        logger.info(f"[LLMService] LlamaIndex provider: {provider}")

    @property
    def _using_azure(self) -> bool:
        return bool(
            settings.AZURE_OPENAI_ENDPOINT
            and (settings.AZURE_OPENAI_API_KEY or settings.MODEL_API_KEY)
        )

    def _get_client(self, temperature: float = 0.7, max_tokens: int = 4000):
        max_tokens = max(max_tokens, 2000)
        effective_temperature = _temperature_for_model(temperature)
        cache_key = (effective_temperature, max_tokens)
        if cache_key in self._clients:
            return self._clients[cache_key]

        if self._using_azure:
            from llama_index.llms.azure_openai import AzureOpenAI

            client = AzureOpenAI(
                engine=settings.AZURE_OPENAI_DEPLOYMENT,
                model=_active_model(),
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=settings.AZURE_OPENAI_API_KEY or settings.MODEL_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                temperature=effective_temperature,
                max_tokens=max_tokens,
                timeout=settings.LLM_REQUEST_TIMEOUT_S,
                max_retries=settings.LLM_MAX_RETRIES,
                reuse_client=True,
            )
        else:
            api_key = (
                settings.LLM_API_KEY
                or settings.MODEL_API_KEY
                or settings.AZURE_OPENAI_API_KEY
            )
            if settings.LLM_BASE_URL:
                from llama_index.llms.openai_like import OpenAILike

                client = OpenAILike(
                    model=settings.LLM_MODEL or "gpt-4.1-mini",
                    api_key=api_key,
                    api_base=settings.LLM_BASE_URL,
                    context_window=settings.LLM_CONTEXT_WINDOW,
                    is_chat_model=True,
                    is_function_calling_model=False,
                    temperature=effective_temperature,
                    max_tokens=max_tokens,
                    timeout=settings.LLM_REQUEST_TIMEOUT_S,
                    max_retries=settings.LLM_MAX_RETRIES,
                    reuse_client=True,
                )
            else:
                from llama_index.llms.openai import OpenAI

                client = OpenAI(
                    model=settings.LLM_MODEL or "gpt-4.1-mini",
                    api_key=api_key,
                    temperature=effective_temperature,
                    max_tokens=max_tokens,
                    timeout=settings.LLM_REQUEST_TIMEOUT_S,
                    max_retries=settings.LLM_MAX_RETRIES,
                    reuse_client=True,
                )

        self._clients[cache_key] = client
        return client

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        max_tokens = max(max_tokens, 2000)
        queued_at = time.perf_counter()
        async with self._request_semaphore:
            started_at = time.perf_counter()
            client = self._get_client(temperature=temperature, max_tokens=max_tokens)
            response = await client.achat(_convert_messages(messages))
            answer, finish_reason, reasoning_tokens = _response_details(response)

            if len(answer) < self.EMPTY_RESPONSE_MIN_CHARS and (
                finish_reason == "length" or reasoning_tokens > max_tokens * 0.5
            ):
                retry_tokens = min(max_tokens * self.RETRY_TOKEN_MULTIPLIER, 6000)
                logger.warning(
                    f"[LLMService] Token starvation; retrying with {retry_tokens} tokens"
                )
                retry_client = self._get_client(
                    temperature=temperature, max_tokens=retry_tokens
                )
                retry_response = await retry_client.achat(_convert_messages(messages))
                answer, _, _ = _response_details(retry_response)

            logger.info(
                "[LLMService] Completion: %s chars | queue=%.1fms provider=%.1fms",
                len(answer),
                (started_at - queued_at) * 1000,
                (time.perf_counter() - started_at) * 1000,
            )
            return answer

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ):
        queued_at = time.perf_counter()
        async with self._request_semaphore:
            started_at = time.perf_counter()
            client = self._get_client(
                temperature=temperature, max_tokens=max(max_tokens, 2000)
            )
            stream = await client.astream_chat(_convert_messages(messages))
            try:
                async for event in stream:
                    if event.delta:
                        yield event.delta
            finally:
                logger.info(
                    "[LLMService] Stream: queue=%.1fms provider=%.1fms",
                    (started_at - queued_at) * 1000,
                    (time.perf_counter() - started_at) * 1000,
                )


llm_service = LLMService()
