"""
Text embeddings over any OpenAI-compatible /embeddings API.

EMBEDDING_BASE_URL / EMBEDDING_API_KEY default to the small chat model's, so one
provider can serve both. Requests are batched, a few run at once, and query
embeddings are cached briefly (the same question is often asked twice).
"""
import asyncio
import hashlib
from typing import List

import openai

from config.settings import settings
from utils.logger import logger

_QUERY_CACHE_TTL = 3600


class EmbeddingService:
    def __init__(self):
        self._client = None
        self._sem = None

    @property
    def client(self) -> openai.AsyncOpenAI:
        if self._client is None:
            base_url = settings.EMBEDDING_BASE_URL or settings.SMALL_LLM_BASE_URL or settings.LLM_BASE_URL or None
            api_key = settings.EMBEDDING_API_KEY or settings.SMALL_LLM_API_KEY or settings.LLM_API_KEY or "not-set"
            self._client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=60, max_retries=3)
            logger.info(f"[Embeddings] {settings.EMBEDDING_MODEL} ({settings.EMBEDDING_DIMENSION}d) @ {base_url or 'api.openai.com'}")
        return self._client

    @property
    def _semaphore(self) -> asyncio.Semaphore:
        if self._sem is None:
            self._sem = asyncio.Semaphore(max(1, settings.MAX_GLOBAL_EMBEDDINGS))
        return self._sem

    async def _embed_batch(self, batch: List[str]) -> List[List[float]]:
        kwargs = {"model": settings.EMBEDDING_MODEL, "input": batch}
        if settings.EMBEDDING_SEND_DIMENSIONS:
            kwargs["dimensions"] = settings.EMBEDDING_DIMENSION
        async with self._semaphore:
            resp = await self.client.embeddings.create(**kwargs)
        vectors = [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
        if vectors and len(vectors[0]) != settings.EMBEDDING_DIMENSION:
            raise ValueError(
                f"Embedding model returned {len(vectors[0])} dimensions but EMBEDDING_DIMENSION is "
                f"{settings.EMBEDDING_DIMENSION}. Set them to match (or EMBEDDING_SEND_DIMENSIONS=true).")
        return vectors

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Embeddings for many texts, in order. Empty strings become a single space."""
        if not texts:
            return []
        clean = [t if t and t.strip() else " " for t in texts]
        size = max(1, settings.EMBEDDING_BATCH_SIZE)
        batches = [clean[i:i + size] for i in range(0, len(clean), size)]
        results = await asyncio.gather(*[self._embed_batch(b) for b in batches])
        return [v for batch in results for v in batch]

    async def generate_embedding(self, text: str) -> List[float]:
        """One embedding (a search query), cached for an hour."""
        from utils.cache import get_cache
        key = "emb:" + hashlib.sha256(f"{settings.EMBEDDING_MODEL}|{text}".encode()).hexdigest()
        cache = get_cache()
        cached = await cache.get(key)
        if cached:
            return cached
        vector = (await self.generate_embeddings([text]))[0]
        await cache.set(key, vector, ttl=_QUERY_CACHE_TTL)
        return vector

    def shutdown(self):
        pass   # nothing to release; kept for main.py's shutdown hook


embedding_service = EmbeddingService()
