from langchain_openai import OpenAIEmbeddings
from config.settings import settings
from typing import List, Optional
from utils.logger import logger
import os
import hashlib
import json
from contextlib import contextmanager


@contextmanager
def _null_ctx():
    """No-op context manager used when telemetry is unavailable."""
    yield None

class EmbeddingService:
    """
    High-performance async embedding service.

    Optimizations:
    - Uses native async IO (aembed_documents/aembed_query)
    - Connection reuse via persistent client
    - Redis caching for embedding results (30-day TTL)
    - Cache hit rate tracking
    """

    def __init__(self, redis_manager=None):
        os.environ["OPENAI_API_KEY"] = settings.EMBEDDING_API_KEY
        
        self.embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.EMBEDDING_API_KEY,
            openai_api_base=settings.EMBEDDING_BASE_URL
        )
        
        # Redis cache manager (optional for graceful degradation)
        self.redis_manager = redis_manager
        self.cache_ttl = 2592000  # 30 days
        
        # Cache hit rate tracking
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_requests = 0
        
        # Telemetry service (lazy loaded to avoid circular imports)
        self._telemetry = None
        
        logger.info("[EmbeddingService] Initialized with async IO native support and Redis caching")
    
    def _get_telemetry(self):
        """Lazy load telemetry service to avoid circular imports."""
        if self._telemetry is None:
            try:
                from core.telemetry import get_telemetry_service
                self._telemetry = get_telemetry_service()
            except Exception as e:
                logger.debug(f"Telemetry service not available: {e}")
        return self._telemetry
    
    def _add_passage_prefix(self, texts: List[str]) -> List[str]:
        """Add 'passage: ' prefix for E5 instruct models (document/passage embedding)."""
        return [f"passage: {t}" for t in texts]

    def _add_query_prefix(self, text: str) -> str:
        """Add 'query: ' prefix for E5 instruct models (search query embedding)."""
        return f"query: {text}"
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate cache key from text hash (sha256)."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"emb:{text_hash}"
    
    async def _get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Retrieve embedding from cache if available."""
        if not self.redis_manager or not self.redis_manager.is_available:
            return None
        
        cache_key = self._generate_cache_key(text)
        cached_data = await self.redis_manager.get(cache_key)
        
        if cached_data:
            try:
                data = json.loads(cached_data)
                return data.get("embedding")
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode cached embedding for key: {cache_key}")
                return None
        
        return None
    
    async def _cache_embedding(self, text: str, embedding: List[float]) -> None:
        """Store embedding in cache with 30-day TTL."""
        if not self.redis_manager or not self.redis_manager.is_available:
            return
        
        cache_key = self._generate_cache_key(text)
        cache_data = {
            "text_hash": hashlib.sha256(text.encode()).hexdigest(),
            "embedding": embedding,
            "model": settings.EMBEDDING_MODEL
        }
        
        await self.redis_manager.set(
            cache_key,
            json.dumps(cache_data),
            ttl=self.cache_ttl
        )
    
    def _track_cache_hit(self) -> None:
        """Track cache hit and log statistics every 100 requests."""
        self.cache_hits += 1
        self.total_requests += 1
        self._log_cache_stats()
    
    def _track_cache_miss(self) -> None:
        """Track cache miss and log statistics every 100 requests."""
        self.cache_misses += 1
        self.total_requests += 1
        self._log_cache_stats()
    
    def _log_cache_stats(self) -> None:
        """Log cache statistics every 100 requests."""
        if self.total_requests % 100 == 0:
            hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0.0
            logger.info(
                f"[EmbeddingService] Cache stats - Total: {self.total_requests}, "
                f"Hits: {self.cache_hits}, Misses: {self.cache_misses}, "
                f"Hit Rate: {hit_rate:.2f}%"
            )
            
            # Log success metric when hit rate exceeds 80%
            if hit_rate > 80:
                logger.info(f"[EmbeddingService] SUCCESS: Cache hit rate exceeds 80% ({hit_rate:.2f}%)")
    
    def get_cache_stats(self) -> dict:
        """Get current cache statistics."""
        hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0.0
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": round(hit_rate, 2)
        }

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts (documents/passages).

        Uses async IO for non-blocking concurrent API calls.
        E5 instruct models require 'passage: ' prefix for document chunks.
        Checks cache before making API calls.
        """
        try:
            if not texts:
                return []

            import time
            start_time = time.time()

            telemetry = self._get_telemetry()
            span_props = {
                "operation": "generate_embeddings",
                "batch_size": len(texts),
                "model": settings.EMBEDDING_MODEL,
            }

            with (telemetry.start_span("embedding.generate_batch", properties=span_props) if telemetry else _null_ctx()) as span:
                embeddings = []
                texts_to_generate = []
                text_indices = []

                # Check cache for each text
                for i, text in enumerate(texts):
                    prefixed_text = self._add_passage_prefix([text])[0]
                    cached_embedding = await self._get_cached_embedding(prefixed_text)

                    if cached_embedding:
                        embeddings.append(cached_embedding)
                        self._track_cache_hit()
                    else:
                        embeddings.append(None)  # Placeholder
                        texts_to_generate.append(text)
                        text_indices.append(i)
                        self._track_cache_miss()

                # Generate embeddings for cache misses
                if texts_to_generate:
                    prefixed_texts = self._add_passage_prefix(texts_to_generate)
                    generated_embeddings = await self.embeddings.aembed_documents(prefixed_texts)

                    # Store in cache and update results
                    for idx, embedding in zip(text_indices, generated_embeddings):
                        embeddings[idx] = embedding
                        prefixed_text = self._add_passage_prefix([texts[idx]])[0]
                        await self._cache_embedding(prefixed_text, embedding)

                # Track embedding throughput
                duration = time.time() - start_time
                cache_hits = len(texts) - len(texts_to_generate)
                cache_misses = len(texts_to_generate)

                if span:
                    span.set_attribute("cache_hits", cache_hits)
                    span.set_attribute("cache_misses", cache_misses)
                    span.set_attribute("api_calls_made", len(texts_to_generate))

                if duration > 0:
                    embeddings_per_second = len(texts) / duration
                    self._track_embedding_throughput(
                        embeddings_per_second=embeddings_per_second,
                        batch_size=len(texts),
                        cache_hits=cache_hits,
                        cache_misses=cache_misses,
                    )

                return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text (search query).
        
        E5 instruct models require 'query: ' prefix for search queries.
        Checks cache before making API calls.
        """
        try:
            prefixed_text = self._add_query_prefix(text)

            telemetry = self._get_telemetry()
            span_props = {
                "operation": "generate_embedding",
                "model": settings.EMBEDDING_MODEL,
                "text_length": len(text),
            }

            with (telemetry.start_span("embedding.generate_query", properties=span_props) if telemetry else _null_ctx()) as span:
                # Check cache first
                cached_embedding = await self._get_cached_embedding(prefixed_text)
                if cached_embedding:
                    self._track_cache_hit()
                    if span:
                        span.set_attribute("cache_hit", True)
                    return cached_embedding

                # Cache miss - generate embedding
                self._track_cache_miss()
                if span:
                    span.set_attribute("cache_hit", False)
                embedding = await self.embeddings.aembed_query(prefixed_text)

                # Store in cache
                await self._cache_embedding(prefixed_text, embedding)

                return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def shutdown(self):
        """Cleanup resources on shutdown"""
        logger.info("[EmbeddingService] Shut down")
    
    def _track_embedding_throughput(
        self,
        embeddings_per_second: float,
        batch_size: int,
        cache_hits: int,
        cache_misses: int
    ) -> None:
        """
        Track embedding throughput to telemetry service.
        
        Args:
            embeddings_per_second: Number of embeddings generated per second
            batch_size: Size of the batch processed
            cache_hits: Number of cache hits in this batch
            cache_misses: Number of cache misses in this batch
        """
        telemetry = self._get_telemetry()
        if not telemetry:
            return
        
        try:
            cache_hit_rate = (cache_hits / batch_size * 100) if batch_size > 0 else 0.0
            
            telemetry.track_embedding_throughput(
                embeddings_per_second=embeddings_per_second,
                batch_size=batch_size,
                properties={
                    "model": settings.EMBEDDING_MODEL,
                    "cache_hit_rate": f"{cache_hit_rate:.2f}",
                    "cache_hits": cache_hits,
                    "cache_misses": cache_misses
                }
            )
            
            logger.debug(
                f"[EmbeddingService] Tracked throughput: {embeddings_per_second:.2f} embeddings/s "
                f"(batch_size={batch_size}, cache_hit_rate={cache_hit_rate:.2f}%)"
            )
        except Exception as e:
            logger.error(f"Failed to track embedding throughput: {e}")


# Initialize with Redis manager when available
embedding_service = EmbeddingService()
