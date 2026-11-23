"""
Text embeddings over any OpenAI-compatible /embeddings API, or AWS Bedrock (EMBEDDING_PROVIDER=bedrock).

EMBEDDING_BASE_URL / EMBEDDING_API_KEY default to the small chat model's, so one
provider can serve both. Requests are batched, a few run at once, and query
embeddings are cached briefly (the same question is often asked twice).
"""
import asyncio
import hashlib
import time
from typing import List

import json

import openai

from config.settings import settings
from utils.logger import logger

_QUERY_CACHE_TTL = 3600


def _record(tokens: int, latency_ms: int, ok: bool = True) -> None:
    try:
        from services.telemetry import telemetry
        telemetry.record("embedding", settings.EMBEDDING_MODEL, role="embedding", input_tokens=tokens,
                         latency_ms=latency_ms, ok=ok)
    except Exception:
        pass



class EmbeddingsOff(RuntimeError):
    """Raised when no embedding model is configured; callers fall back to keyword search."""


def embeddings_off() -> bool:
    return (settings.EMBEDDING_PROVIDER or "").lower() == "none"

class EmbeddingService:
    def __init__(self):
        self._client = None
        self._sem = None
        self._bedrock = None
        self._one_sem = None

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

    @property
    def bedrock(self):
        if self._bedrock is None:
            import boto3
            from botocore.config import Config
            self._bedrock = boto3.client("bedrock-runtime", region_name=settings.BEDROCK_REGION,
                                         config=Config(retries={"max_attempts": 6, "mode": "adaptive"},
                                                       max_pool_connections=32))
            logger.info(f"[Embeddings] {settings.EMBEDDING_MODEL} ({settings.EMBEDDING_DIMENSION}d) @ Bedrock {settings.BEDROCK_REGION}")
        return self._bedrock

    def _bedrock_invoke(self, body: dict) -> dict:
        resp = self.bedrock.invoke_model(modelId=settings.EMBEDDING_MODEL, body=json.dumps(body),
                                         contentType="application/json", accept="application/json")
        return json.loads(resp["body"].read())

    async def _bedrock_batch(self, batch: List[str]):
        """Titan takes one text per call (run a few at once); Cohere takes up to 96."""
        model = settings.EMBEDDING_MODEL
        dim = settings.EMBEDDING_DIMENSION
        if "cohere" in model:
            out: List[List[float]] = []
            for i in range(0, len(batch), 96):
                data = await asyncio.to_thread(self._bedrock_invoke, {
                    "texts": [t[:2048] for t in batch[i:i + 96]], "input_type": "search_document",
                    "embedding_types": ["float"], "output_dimension": dim})
                emb = data["embeddings"]
                out.extend(emb["float"] if isinstance(emb, dict) else emb)
            return out, sum(len(t) // 4 for t in batch)

        if self._one_sem is None:
            self._one_sem = asyncio.Semaphore(8)

        async def one(text: str):
            # Titan v2 reads at most 8k tokens (about 50k characters)
            async with self._one_sem:
                return await asyncio.to_thread(self._bedrock_invoke, {"inputText": text[:40000], "dimensions": dim,
                                                                      "normalize": True})
        results = await asyncio.gather(*[one(t) for t in batch])
        return [r["embedding"] for r in results], sum(r.get("inputTextTokenCount", 0) for r in results)

    async def _embed_batch(self, batch: List[str]) -> List[List[float]]:
        if settings.EMBEDDING_PROVIDER == "bedrock":
            async with self._semaphore:
                started = time.perf_counter()
                try:
                    vectors, tokens = await self._bedrock_batch(batch)
                except Exception:
                    _record(0, int((time.perf_counter() - started) * 1000), ok=False)
                    raise
            _record(tokens, int((time.perf_counter() - started) * 1000))
            if vectors and len(vectors[0]) != settings.EMBEDDING_DIMENSION:
                raise ValueError(f"Bedrock returned {len(vectors[0])} dimensions, EMBEDDING_DIMENSION is "
                                 f"{settings.EMBEDDING_DIMENSION}")
            return vectors
        kwargs = {"model": settings.EMBEDDING_MODEL, "input": batch}
        if settings.EMBEDDING_SEND_DIMENSIONS:
            kwargs["dimensions"] = settings.EMBEDDING_DIMENSION
        async with self._semaphore:
            started = time.perf_counter()
            try:
                resp = await self.client.embeddings.create(**kwargs)
            except Exception:
                _record(0, int((time.perf_counter() - started) * 1000), ok=False)
                raise
        usage = getattr(resp, "usage", None)
        tokens = (getattr(usage, "prompt_tokens", 0) or 0) if usage else sum(len(t) // 4 for t in batch)
        _record(tokens, int((time.perf_counter() - started) * 1000))
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
        if embeddings_off():
            raise EmbeddingsOff("embeddings are switched off (EMBEDDING_PROVIDER=none)")
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
