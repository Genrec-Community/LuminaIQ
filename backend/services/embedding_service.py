from langchain_openai import OpenAIEmbeddings
from config.settings import settings
from typing import List
from utils.logger import logger
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor


class EmbeddingService:
    """
    High-performance embedding service using Native Async HTTP calls.

    Optimizations:
    - Pure async HTTP execution (No ThreadPool blocking or GIL locking)
    - Connection reuse via persistent client
    """

    def __init__(self):
        os.environ["OPENAI_API_KEY"] = settings.EMBEDDING_API_KEY
        
        self.embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.EMBEDDING_API_KEY,
            openai_api_base=settings.EMBEDDING_BASE_URL
        )
        logger.info("[EmbeddingService] Initialized native AsyncOpenAI Embeddings")
    


    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts (documents/passages).

        Uses dedicated thread pool for faster concurrent API calls.
        E5 instruct models require 'passage: ' prefix for document chunks.
        """
        try:
            if not texts:
                return []

            embeddings = await self.embeddings.aembed_documents(texts)
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text (search query).
        
        E5 instruct models require 'query: ' prefix for search queries.
        """
        try:
            return await self.embeddings.aembed_query(text)
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def shutdown(self):
        """Cleanup on shutdown"""
        logger.info("[EmbeddingService] Shut down")


embedding_service = EmbeddingService()
