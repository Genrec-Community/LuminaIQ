from langchain_together import TogetherEmbeddings
from config.settings import settings
from typing import List
from utils.logger import logger
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor


class EmbeddingService:
    """
    High-performance embedding service with dedicated thread pool.

    Optimizations:
    - Dedicated thread pool (not shared default executor)
    - Configurable worker count for parallel API calls
    - Connection reuse via persistent client
    """

    # Optimal workers for I/O-bound embedding API calls
    MAX_WORKERS = 10

    def __init__(self):
        os.environ["TOGETHER_API_KEY"] = settings.TOGETHER_API_KEY
        self.embeddings = TogetherEmbeddings(
            model=settings.EMBEDDING_MODEL, together_api_key=settings.TOGETHER_API_KEY
        )
        # Dedicated thread pool for embedding calls - much faster than default
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS, thread_name_prefix="embedding_worker"
        )
        logger.info(f"[EmbeddingService] Initialized with {self.MAX_WORKERS} workers")

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Uses dedicated thread pool for faster concurrent API calls.
        """
        try:
            if not texts:
                return []

            loop = asyncio.get_running_loop()

            # Run embedding in dedicated thread pool (Together API is sync)
            texts_copy = list(texts)
            embeddings = await loop.run_in_executor(
                self._executor,  # Use dedicated pool, not None (default)
                self.embeddings.embed_documents,
                texts_copy,
            )
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._executor,  # Use dedicated pool
                self.embeddings.embed_query,
                text,
            )
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def shutdown(self):
        """Cleanup thread pool on shutdown"""
        if self._executor:
            self._executor.shutdown(wait=False)
            logger.info("[EmbeddingService] Thread pool shut down")


embedding_service = EmbeddingService()
