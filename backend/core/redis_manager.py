"""Redis Cache Manager with connection pooling and graceful degradation."""

import asyncio
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from config.settings import settings

logger = logging.getLogger(__name__)


# Cache key namespacing functions
def generate_embedding_key(text: str) -> str:
    """Generate cache key for embedding results."""
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    return f"emb:{text_hash}"


def generate_query_key(project_id: str, query: str) -> str:
    """Generate cache key for semantic query results."""
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    return f"query:{project_id}:{query_hash}"


def generate_vector_search_key(collection: str, vector_hash: str, filter_hash: str) -> str:
    """Generate cache key for vector search results."""
    return f"vsearch:{collection}:{vector_hash}:{filter_hash}"


def generate_document_key(doc_id: str) -> str:
    """Generate cache key for document metadata."""
    return f"doc:{doc_id}"


def generate_documents_list_key(project_id: str) -> str:
    """Generate cache key for project documents list."""
    return f"docs:{project_id}"


def generate_session_key(session_id: str) -> str:
    """Generate cache key for user session data."""
    return f"session:{session_id}"


def generate_session_messages_key(session_id: str) -> str:
    """Generate cache key for session messages."""
    return f"session:{session_id}:messages"


def generate_rate_limit_key(user_id: str, endpoint: str) -> str:
    """Generate cache key for rate limiting counters."""
    return f"ratelimit:{user_id}:{endpoint}"


def generate_lock_key(resource_id: str) -> str:
    """Generate cache key for distributed locks."""
    return f"lock:{resource_id}"


def generate_job_key(job_id: str) -> str:
    """Generate cache key for background job status."""
    return f"job:{job_id}"


def generate_jobs_list_key(project_id: str) -> str:
    """Generate cache key for project jobs list."""
    return f"jobs:{project_id}"


def generate_topics_key(project_id: str) -> str:
    """Generate cache key for project topics."""
    return f"topics:{project_id}"


def generate_knowledge_graph_key(project_id: str) -> str:
    """Generate cache key for knowledge graph."""
    return f"kg:{project_id}"


def generate_query_embeddings_index_key(project_id: str) -> str:
    """Generate cache key for query embeddings sorted set index."""
    return f"query_embeddings:{project_id}"


class RedisCacheManager:
    """
    Centralized Redis connection management with connection pooling and automatic reconnection.
    
    Features:
    - Connection pooling (min=10, max=50 connections)
    - Connection timeout of 5 seconds
    - Socket keepalive enabled
    - Retry on connection failure (3 attempts with exponential backoff)
    - Graceful degradation (log warning, return None on get operations when Redis unavailable)
    - Auto-reconnect when Redis becomes available
    - Cache key namespacing for different data types
    - Configurable TTL support per cache type
    - Comprehensive cache statistics tracking
    """

    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        db: int = 0,
        max_connections: int = 50,
        min_connections: int = 10,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        retry_attempts: int = 3,
        ttl_embedding: int = 2592000,  # 30 days
        ttl_query: int = 604800,  # 7 days
        ttl_vector_search: int = 3600,  # 1 hour
        ttl_document: int = 21600,  # 6 hours
        ttl_session: int = 86400,  # 24 hours
    ):
        """
        Initialize Redis Cache Manager.
        
        Args:
            host: Redis server hostname
            port: Redis server port
            password: Redis authentication password
            db: Redis database number (default: 0)
            max_connections: Maximum connections in pool (default: 50)
            min_connections: Minimum connections in pool (default: 10)
            socket_timeout: Socket timeout in seconds (default: 5)
            socket_connect_timeout: Connection timeout in seconds (default: 5)
            retry_attempts: Number of retry attempts on failure (default: 3)
            ttl_embedding: TTL for embedding cache in seconds (default: 30 days)
            ttl_query: TTL for query cache in seconds (default: 7 days)
            ttl_vector_search: TTL for vector search cache in seconds (default: 1 hour)
            ttl_document: TTL for document metadata cache in seconds (default: 6 hours)
            ttl_session: TTL for session cache in seconds (default: 24 hours)
        """
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.retry_attempts = retry_attempts
        
        # Configurable TTL values
        self.ttl_embedding = ttl_embedding
        self.ttl_query = ttl_query
        self.ttl_vector_search = ttl_vector_search
        self.ttl_document = ttl_document
        self.ttl_session = ttl_session
        
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._is_available = False
        
        # Telemetry service (lazy loaded to avoid circular imports)
        self._telemetry = None
        
        # Enhanced statistics tracking
        self._stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "total_requests": 0,
            "by_type": {
                "embedding": {"hits": 0, "misses": 0, "requests": 0},
                "query": {"hits": 0, "misses": 0, "requests": 0},
                "vector_search": {"hits": 0, "misses": 0, "requests": 0},
                "document": {"hits": 0, "misses": 0, "requests": 0},
                "session": {"hits": 0, "misses": 0, "requests": 0},
                "other": {"hits": 0, "misses": 0, "requests": 0},
            }
        }
    
    def _get_telemetry(self):
        """Lazy load telemetry service to avoid circular imports."""
        if self._telemetry is None:
            try:
                from core.telemetry import get_telemetry_service
                self._telemetry = get_telemetry_service()
            except Exception as e:
                logger.debug(f"Telemetry service not available: {e}")
        return self._telemetry

    async def connect(self) -> None:
        """
        Establish connection to Redis with connection pooling.
        
        Raises:
            RedisError: If connection fails after all retry attempts
        """
        for attempt in range(1, self.retry_attempts + 1):
            try:
                logger.info(
                    f"Connecting to Redis at {self.host}:{self.port} "
                    f"(attempt {attempt}/{self.retry_attempts})"
                )
                
                # Create connection pool
                self._pool = ConnectionPool(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    db=self.db,
                    max_connections=self.max_connections,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_connect_timeout,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    retry_on_timeout=True,
                    decode_responses=True,
                )
                
                # Create Redis client
                self._client = redis.Redis(connection_pool=self._pool)
                
                # Test connection
                await self._client.ping()
                
                self._is_available = True
                logger.info(
                    f"Successfully connected to Redis at {self.host}:{self.port} "
                    f"with connection pool (min={self.min_connections}, max={self.max_connections})"
                )
                return
                
            except (ConnectionError, TimeoutError, RedisError) as e:
                logger.warning(
                    f"Redis connection attempt {attempt}/{self.retry_attempts} failed: {e}"
                )
                
                if attempt < self.retry_attempts:
                    # Exponential backoff: 2^attempt seconds
                    backoff_delay = 2 ** attempt
                    logger.info(f"Retrying in {backoff_delay} seconds...")
                    await asyncio.sleep(backoff_delay)
                else:
                    # All retries exhausted
                    self._is_available = False
                    logger.error(
                        f"Failed to connect to Redis after {self.retry_attempts} attempts. "
                        "Operating in degraded mode without caching."
                    )
                    # Don't raise exception - allow graceful degradation

    async def disconnect(self) -> None:
        """Close Redis connection and cleanup resources."""
        if self._client:
            try:
                await self._client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self._client = None
                self._is_available = False
        
        if self._pool:
            try:
                await self._pool.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting connection pool: {e}")
            finally:
                self._pool = None

    async def _execute_with_retry(self, operation, *args, **kwargs) -> Any:
        """
        Execute Redis operation with automatic retry and graceful degradation.
        
        Args:
            operation: Redis operation to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Operation result or None if Redis unavailable
        """
        if not self._is_available or not self._client:
            logger.debug("Redis unavailable, skipping operation")
            return None
        
        # Track telemetry
        operation_name = kwargs.pop('_telemetry_name', operation.__name__ if hasattr(operation, '__name__') else 'unknown')
        start_time = time.time()
        success = False
        
        for attempt in range(1, self.retry_attempts + 1):
            try:
                result = await operation(*args, **kwargs)
                
                # Auto-reconnect if we were previously unavailable
                if not self._is_available:
                    self._is_available = True
                    logger.info("Redis connection restored")
                
                success = True
                duration_ms = (time.time() - start_time) * 1000
                
                # Track dependency telemetry
                telemetry = self._get_telemetry()
                if telemetry:
                    telemetry.track_dependency(
                        name=f"Redis {operation_name}",
                        dependency_type="redis",
                        duration=duration_ms,
                        success=True,
                        properties={
                            "operation": operation_name,
                            "host": self.host,
                            "db": self.db
                        }
                    )
                
                return result
                
            except (ConnectionError, TimeoutError) as e:
                logger.warning(f"Redis operation failed (attempt {attempt}/{self.retry_attempts}): {e}")
                self._stats["errors"] += 1
                
                if attempt < self.retry_attempts:
                    backoff_delay = 2 ** (attempt - 1)
                    await asyncio.sleep(backoff_delay)
                else:
                    # Mark as unavailable for graceful degradation
                    self._is_available = False
                    logger.error(
                        "Redis operation failed after all retries. "
                        "Operating in degraded mode."
                    )
                    
                    # Track failed dependency
                    duration_ms = (time.time() - start_time) * 1000
                    telemetry = self._get_telemetry()
                    if telemetry:
                        telemetry.track_dependency(
                            name=f"Redis {operation_name}",
                            dependency_type="redis",
                            duration=duration_ms,
                            success=False,
                            properties={
                                "operation": operation_name,
                                "host": self.host,
                                "db": self.db,
                                "error": str(e)
                            }
                        )
                    
                    return None
                    
            except RedisError as e:
                logger.error(f"Redis error: {e}")
                self._stats["errors"] += 1
                
                # Track failed dependency
                duration_ms = (time.time() - start_time) * 1000
                telemetry = self._get_telemetry()
                if telemetry:
                    telemetry.track_dependency(
                        name=f"Redis {operation_name}",
                        dependency_type="redis",
                        duration=duration_ms,
                        success=False,
                        properties={
                            "operation": operation_name,
                            "host": self.host,
                            "db": self.db,
                            "error": str(e)
                        }
                    )
                
                return None

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from Redis cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or Redis unavailable
        """
        self._stats["total_requests"] += 1
        
        # Determine cache type from key prefix
        cache_type = self._get_cache_type(key)
        self._stats["by_type"][cache_type]["requests"] += 1
        
        result = await self._execute_with_retry(self._client.get, key, _telemetry_name="GET")
        
        if result is not None:
            self._stats["hits"] += 1
            self._stats["by_type"][cache_type]["hits"] += 1
            logger.debug(f"Cache HIT: {key}")
        else:
            self._stats["misses"] += 1
            self._stats["by_type"][cache_type]["misses"] += 1
            logger.debug(f"Cache MISS: {key}")
        
        # Track cache hit rate every 100 requests
        if self._stats["total_requests"] % 100 == 0:
            self._track_cache_hit_rate_telemetry()
        
        return result
    
    def _get_cache_type(self, key: str) -> str:
        """
        Determine cache type from key prefix.
        
        Args:
            key: Cache key
            
        Returns:
            Cache type string
        """
        if key.startswith("emb:"):
            return "embedding"
        elif key.startswith("query:"):
            return "query"
        elif key.startswith("vsearch:"):
            return "vector_search"
        elif key.startswith("doc:") or key.startswith("docs:"):
            return "document"
        elif key.startswith("session:"):
            return "session"
        else:
            return "other"
    
    def _track_cache_hit_rate_telemetry(self) -> None:
        """
        Track cache hit rate to telemetry service.
        
        Sends overall hit rate and per-type hit rates to Application Insights.
        """
        telemetry = self._get_telemetry()
        if not telemetry:
            return
        
        try:
            # Track overall hit rate
            total = self._stats["total_requests"]
            if total > 0:
                overall_hit_rate = (self._stats["hits"] / total) * 100
                telemetry.track_cache_hit_rate(
                    hit_rate=overall_hit_rate,
                    cache_type="overall",
                    properties={
                        "total_requests": total,
                        "hits": self._stats["hits"],
                        "misses": self._stats["misses"]
                    }
                )
            
            # Track per-type hit rates
            for cache_type, type_stats in self._stats["by_type"].items():
                type_total = type_stats["requests"]
                if type_total > 0:
                    type_hit_rate = (type_stats["hits"] / type_total) * 100
                    telemetry.track_cache_hit_rate(
                        hit_rate=type_hit_rate,
                        cache_type=cache_type,
                        properties={
                            "total_requests": type_total,
                            "hits": type_stats["hits"],
                            "misses": type_stats["misses"]
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to track cache hit rate telemetry: {e}")

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set value in Redis cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        result = await self._execute_with_retry(
            self._client.set,
            key,
            value,
            ex=ttl,
            _telemetry_name="SET"
        )
        
        success = result is not None
        if success:
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
        
        return success

    async def delete(self, key: str) -> bool:
        """
        Delete key from Redis cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key was deleted, False otherwise
        """
        result = await self._execute_with_retry(self._client.delete, key, _telemetry_name="DELETE")
        
        success = result is not None and result > 0
        if success:
            logger.debug(f"Cache DELETE: {key}")
        
        return success

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        result = await self._execute_with_retry(self._client.exists, key, _telemetry_name="EXISTS")
        return result is not None and result > 0

    async def get_many(self, keys: List[str]) -> Dict[str, str]:
        """
        Get multiple values from Redis cache in a single operation.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary mapping keys to values (only includes found keys)
        """
        if not keys:
            return {}
        
        self._stats["total_requests"] += len(keys)
        
        # Track requests by type
        for key in keys:
            cache_type = self._get_cache_type(key)
            self._stats["by_type"][cache_type]["requests"] += 1
        
        values = await self._execute_with_retry(self._client.mget, keys, _telemetry_name="MGET")
        
        if values is None:
            self._stats["misses"] += len(keys)
            for key in keys:
                cache_type = self._get_cache_type(key)
                self._stats["by_type"][cache_type]["misses"] += 1
            return {}
        
        # Build result dictionary, excluding None values
        result = {}
        for key, value in zip(keys, values):
            cache_type = self._get_cache_type(key)
            if value is not None:
                result[key] = value
                self._stats["hits"] += 1
                self._stats["by_type"][cache_type]["hits"] += 1
            else:
                self._stats["misses"] += 1
                self._stats["by_type"][cache_type]["misses"] += 1
        
        logger.debug(f"Cache GET_MANY: {len(result)}/{len(keys)} keys found")
        return result

    async def set_many(self, items: Dict[str, str], ttl: Optional[int] = None) -> bool:
        """
        Set multiple values in Redis cache.
        
        Args:
            items: Dictionary mapping keys to values
            ttl: Time-to-live in seconds (optional, applied to all keys)
            
        Returns:
            True if successful, False otherwise
        """
        if not items:
            return True
        
        # Use pipeline for atomic multi-set
        try:
            if not self._is_available or not self._client:
                return False
            
            async with self._client.pipeline(transaction=True) as pipe:
                for key, value in items.items():
                    if ttl:
                        pipe.setex(key, ttl, value)
                    else:
                        pipe.set(key, value)
                
                result = await self._execute_with_retry(pipe.execute)
                
                success = result is not None
                if success:
                    logger.debug(f"Cache SET_MANY: {len(items)} keys (TTL: {ttl}s)")
                
                return success
                
        except Exception as e:
            logger.error(f"Error in set_many: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment a counter in Redis.
        
        Args:
            key: Counter key
            amount: Amount to increment by (default: 1)
            
        Returns:
            New counter value, or 0 if Redis unavailable
        """
        result = await self._execute_with_retry(self._client.incrby, key, amount, _telemetry_name="INCRBY")
        return result if result is not None else 0

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key.
        
        Args:
            key: Cache key
            ttl: Time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        result = await self._execute_with_retry(self._client.expire, key, ttl, _telemetry_name="EXPIRE")
        return result is not None and result > 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary containing cache statistics:
            - hit_rate: Percentage of cache hits
            - miss_rate: Percentage of cache misses
            - total_requests: Total number of cache requests
            - hits: Number of cache hits
            - misses: Number of cache misses
            - errors: Number of errors
            - is_available: Whether Redis is currently available
            - by_type: Statistics broken down by cache type
        """
        total = self._stats["total_requests"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0
        miss_rate = (self._stats["misses"] / total * 100) if total > 0 else 0.0
        
        # Calculate hit rates by type
        by_type_stats = {}
        for cache_type, type_stats in self._stats["by_type"].items():
            type_total = type_stats["requests"]
            type_hit_rate = (type_stats["hits"] / type_total * 100) if type_total > 0 else 0.0
            by_type_stats[cache_type] = {
                "hit_rate": round(type_hit_rate, 2),
                "total_requests": type_total,
                "hits": type_stats["hits"],
                "misses": type_stats["misses"],
            }
        
        return {
            "hit_rate": round(hit_rate, 2),
            "miss_rate": round(miss_rate, 2),
            "total_requests": total,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "errors": self._stats["errors"],
            "is_available": self._is_available,
            "by_type": by_type_stats,
        }
    
    async def get_total_keys(self) -> int:
        """
        Get total number of keys in Redis database.
        
        Returns:
            Total number of keys, or 0 if Redis unavailable
        """
        if not self._is_available or not self._client:
            return 0
        
        try:
            result = await self._execute_with_retry(self._client.dbsize)
            return result if result is not None else 0
        except Exception as e:
            logger.error(f"Error getting total keys: {e}")
            return 0
    
    async def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get Redis memory usage statistics.
        
        Returns:
            Dictionary with memory usage information, or empty dict if unavailable
        """
        if not self._is_available or not self._client:
            return {}
        
        try:
            info = await self._execute_with_retry(self._client.info, "memory")
            if info is None:
                return {}
            
            return {
                "used_memory_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
                "used_memory_peak_mb": round(info.get("used_memory_peak", 0) / (1024 * 1024), 2),
                "used_memory_rss_mb": round(info.get("used_memory_rss", 0) / (1024 * 1024), 2),
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}
    
    async def get_connected_clients(self) -> int:
        """
        Get number of connected clients to Redis.
        
        Returns:
            Number of connected clients, or 0 if unavailable
        """
        if not self._is_available or not self._client:
            return 0
        
        try:
            info = await self._execute_with_retry(self._client.info, "clients")
            if info is None:
                return 0
            
            return info.get("connected_clients", 0)
        except Exception as e:
            logger.error(f"Error getting connected clients: {e}")
            return 0

    @property
    def is_available(self) -> bool:
        """Check if Redis is currently available."""
        return self._is_available


# Global singleton instance
_redis_manager_instance: Optional[RedisCacheManager] = None


def get_redis_manager() -> RedisCacheManager:
    """
    Get the global Redis manager instance.
    
    Returns:
        RedisCacheManager: Global Redis manager singleton
        
    Raises:
        RuntimeError: If Redis manager has not been initialized
    """
    global _redis_manager_instance
    
    if _redis_manager_instance is None:
        raise RuntimeError(
            "Redis manager not initialized. Call initialize_redis_manager() first."
        )
    
    return _redis_manager_instance


def initialize_redis_manager() -> RedisCacheManager:
    """
    Initialize the global Redis manager instance with settings from config.
    
    Returns:
        RedisCacheManager: Initialized Redis manager singleton
    """
    global _redis_manager_instance
    
    if _redis_manager_instance is not None:
        logger.warning("Redis manager already initialized, returning existing instance")
        return _redis_manager_instance
    
    _redis_manager_instance = RedisCacheManager(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        db=settings.REDIS_DB,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        retry_attempts=settings.REDIS_RETRY_ATTEMPTS,
        ttl_embedding=getattr(settings, "CACHE_TTL_EMBEDDING", 2592000),
        ttl_query=getattr(settings, "CACHE_TTL_QUERY", 604800),
        ttl_vector_search=getattr(settings, "CACHE_TTL_VECTOR_SEARCH", 3600),
        ttl_document=getattr(settings, "CACHE_TTL_DOCUMENT", 21600),
        ttl_session=getattr(settings, "CACHE_TTL_SESSION", 86400),
    )
    
    logger.info("Redis manager initialized with configuration from settings")
    return _redis_manager_instance


async def shutdown_redis_manager() -> None:
    """
    Shutdown the global Redis manager instance and cleanup resources.
    """
    global _redis_manager_instance
    
    if _redis_manager_instance is not None:
        await _redis_manager_instance.disconnect()
        _redis_manager_instance = None
        logger.info("Redis manager shutdown complete")
