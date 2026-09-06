from config.settings import settings
from typing import List
from utils.logger import logger
import asyncio
from concurrent.futures import ThreadPoolExecutor


class EmbeddingService:
    """
    Client-side embedding service (Azure / OpenAI-compatible).

    NOTE: The primary embedding path is Qdrant Cloud Inference
    (settings.QDRANT_CLOUD_INFERENCE=true) — vectors are generated
    server-side via qdrant_service.upsert_texts / search_by_text, so this
    service is NOT used for uploads or search in that mode. No local
    embedding model is required.

    This service remains for:
    - "azure": AzureOpenAIEmbeddings (legacy production path, 1536-dim).
    - "openai": OpenAI-compatible API fallback (OpenRouter etc.).
    """

    # Optimal workers for I/O-bound embedding API calls
    MAX_WORKERS_BATCH = 15  # Increased from 3 to handle large books significantly faster
    MAX_WORKERS_SEARCH = 2

    def __init__(self):
        self._embeddings_instance = None
        # Dedicated thread pool for batch embedding calls (document processing)
        self._batch_executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS_BATCH, thread_name_prefix="embed_batch"
        )
        # Dedicated thread pool for search queries (user-facing, prevents starvation)
        self._search_executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS_SEARCH, thread_name_prefix="embed_search"
        )

    @property
    def embeddings(self):
        if self._embeddings_instance is not None:
            return self._embeddings_instance

        azure_key = settings.AZURE_OPENAI_API_KEY or settings.MODEL_API_KEY
        if settings.AZURE_OPENAI_ENDPOINT and azure_key:
            from langchain_openai import AzureOpenAIEmbeddings

            self._embeddings_instance = AzureOpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                api_key=azure_key,
                openai_api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_deployment=settings.AZURE_OPENAI_EMBED_DEPLOYMENT,
            )
            logger.info(
                f"[EmbeddingService] Initialized with AzureOpenAIEmbeddings "
                f"| model={settings.EMBEDDING_MODEL} "
                f"| deployment={settings.AZURE_OPENAI_EMBED_DEPLOYMENT}"
            )
        else:
            from langchain_openai import OpenAIEmbeddings

            fallback_key = (
                settings.EMBEDDING_API_KEY
                or settings.MODEL_API_KEY
                or settings.LLM_API_KEY
                or settings.AZURE_OPENAI_API_KEY
            )
            fallback_base = settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL or None

            if not fallback_key:
                raise RuntimeError(
                    "No client-side embedding provider configured, and "
                    "QDRANT_CLOUD_INFERENCE is disabled. Either enable "
                    "QDRANT_CLOUD_INFERENCE=true (recommended — server-side "
                    "embeddings, no local model) or set EMBEDDING_API_KEY / "
                    "AZURE_OPENAI_* credentials."
                )

            self._embeddings_instance = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL or "text-embedding-3-small",
                openai_api_key=fallback_key,
                openai_api_base=fallback_base,
            )
            logger.info(
                f"[EmbeddingService] Initialized with fallback OpenAIEmbeddings "
                f"| model={settings.EMBEDDING_MODEL}"
            )
        return self._embeddings_instance

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts (documents/passages).

        Uses dedicated thread pool for faster concurrent API calls.
        """
        try:
            if not texts:
                return []

            loop = asyncio.get_running_loop()

            embeddings = await loop.run_in_executor(
                self._batch_executor,  # Use dedicated batch pool
                self.embeddings.embed_documents,
                texts,
            )
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text (search query)."""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._search_executor,  # Use dedicated search pool
                self.embeddings.embed_query,
                text,
            )
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def shutdown(self):
        """Cleanup thread pools on shutdown"""
        if hasattr(self, '_batch_executor') and self._batch_executor:
            self._batch_executor.shutdown(wait=False)
        if hasattr(self, '_search_executor') and self._search_executor:
            self._search_executor.shutdown(wait=False)
        logger.info("[EmbeddingService] Thread pools shut down")


embedding_service = EmbeddingService()
