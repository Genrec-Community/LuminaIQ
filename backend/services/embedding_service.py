from langchain_openai import OpenAIEmbeddings
from config.settings import settings
from typing import List
from utils.logger import logger
import os

class EmbeddingService:
    """
    High-performance async embedding service.

    Optimizations:
    - Uses native async IO (aembed_documents/aembed_query)
    - Connection reuse via persistent client
    """

    def __init__(self):
        os.environ["OPENAI_API_KEY"] = settings.EMBEDDING_API_KEY
        
        self.embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.EMBEDDING_API_KEY,
            openai_api_base=settings.EMBEDDING_BASE_URL
        )
        logger.info("[EmbeddingService] Initialized with async IO native support")
    
    def _add_passage_prefix(self, texts: List[str]) -> List[str]:
        """Add 'passage: ' prefix for E5 instruct models (document/passage embedding)."""
        return [f"passage: {t}" for t in texts]

    def _add_query_prefix(self, text: str) -> str:
        """Add 'query: ' prefix for E5 instruct models (search query embedding)."""
        return f"query: {text}"

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts (documents/passages).

        Uses async IO for non-blocking concurrent API calls.
        E5 instruct models require 'passage: ' prefix for document chunks.
        """
        try:
            if not texts:
                return []

            # Add E5 instruction prefix for passages
            prefixed_texts = self._add_passage_prefix(texts)
            embeddings = await self.embeddings.aembed_documents(prefixed_texts)
            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text (search query).
        
        E5 instruct models require 'query: ' prefix for search queries.
        """
        try:
            prefixed_text = self._add_query_prefix(text)
            return await self.embeddings.aembed_query(prefixed_text)
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def shutdown(self):
        """Cleanup resources on shutdown"""
        logger.info("[EmbeddingService] Shut down")


embedding_service = EmbeddingService()
