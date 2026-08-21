"""Native async LlamaIndex embeddings shared by ingestion and retrieval."""

import asyncio
import random

from typing import List

from config.settings import settings
from utils.embedding_scheduler import is_transient_embedding_error
from utils.logger import logger


class EmbeddingService:
    def __init__(self):
        azure_key = settings.AZURE_OPENAI_API_KEY or settings.MODEL_API_KEY
        if settings.AZURE_OPENAI_ENDPOINT and azure_key:
            from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
            from openai import AsyncAzureOpenAI

            self._azure_async_client = AsyncAzureOpenAI(
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                azure_deployment=settings.AZURE_OPENAI_EMBED_DEPLOYMENT,
                api_key=azure_key,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                timeout=settings.EMBEDDING_REQUEST_TIMEOUT_S,
                max_retries=0,
            )

            self.embed_model = AzureOpenAIEmbedding(
                model=settings.EMBEDDING_MODEL,
                azure_deployment=settings.AZURE_OPENAI_EMBED_DEPLOYMENT,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=azure_key,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                dimensions=settings.EMBEDDING_DIMENSION,
                embed_batch_size=settings.EMBEDDING_BATCH_SIZE,
                timeout=settings.EMBEDDING_REQUEST_TIMEOUT_S,
                max_retries=0,
                reuse_client=True,
            )
            # The pinned Azure integration omits timeout/retry values when it
            # creates its async SDK client. Inject the scheduler-controlled one.
            self.embed_model._aclient = self._azure_async_client
            provider = "Azure OpenAI"
        else:
            api_key = (
                settings.EMBEDDING_API_KEY
                or settings.MODEL_API_KEY
                or settings.LLM_API_KEY
            )
            api_base = settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL or None
            if api_base:
                from llama_index.embeddings.openai_like import OpenAILikeEmbedding

                self.embed_model = OpenAILikeEmbedding(
                    model_name=settings.EMBEDDING_MODEL,
                    api_key=api_key,
                    api_base=api_base,
                    dimensions=settings.EMBEDDING_DIMENSION,
                    embed_batch_size=settings.EMBEDDING_BATCH_SIZE,
                    timeout=settings.EMBEDDING_REQUEST_TIMEOUT_S,
                    max_retries=0,
                    reuse_client=True,
                )
            else:
                from llama_index.embeddings.openai import OpenAIEmbedding

                self.embed_model = OpenAIEmbedding(
                    model=settings.EMBEDDING_MODEL or "text-embedding-3-small",
                    api_key=api_key,
                    dimensions=settings.EMBEDDING_DIMENSION,
                    embed_batch_size=settings.EMBEDDING_BATCH_SIZE,
                    timeout=settings.EMBEDDING_REQUEST_TIMEOUT_S,
                    max_retries=0,
                    reuse_client=True,
                )
            provider = "OpenAI-compatible"

        logger.info(
            f"[EmbeddingService] LlamaIndex provider: {provider} | "
            f"model={settings.EMBEDDING_MODEL}"
        )

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return await self.embed_model.aget_text_embedding_batch(
            texts, show_progress=False
        )

    async def generate_embedding(self, text: str) -> List[float]:
        for attempt in range(settings.EMBEDDING_QUERY_MAX_RETRIES + 1):
            try:
                return await self.embed_model.aget_query_embedding(text)
            except Exception as error:
                if (
                    not is_transient_embedding_error(error)
                    or attempt >= settings.EMBEDDING_QUERY_MAX_RETRIES
                ):
                    raise
                delay = (2**attempt) * random.uniform(0.75, 1.0)
                logger.warning(
                    f"[EmbeddingService] Query embedding retry {attempt + 1}/"
                    f"{settings.EMBEDDING_QUERY_MAX_RETRIES} in {delay:.1f}s: {error}"
                )
                await asyncio.sleep(delay)

        raise RuntimeError("Query embedding retry loop exited unexpectedly")

    def shutdown(self):
        # LlamaIndex reuses its async OpenAI client for the process lifetime.
        logger.info(
            "[EmbeddingService] LlamaIndex client shutdown delegated to runtime"
        )


embedding_service = EmbeddingService()
