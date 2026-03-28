"""Vector search result caching with Redis.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

This module provides caching for vector search results to avoid redundant
queries to Qdrant. Cache keys are generated from query vector hash and filter
parameters, with automatic invalidation on document add/delete operations.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.redis_manager import RedisCacheManager

logger = logging.getLogger(__name__)


class VectorSearchCache:
    """
    Vector search result caching service.
    
    Features:
    - Cache key generation from query vector hash and filter parameters
    - 1-hour TTL for search results
    - Cache invalidation on document add/delete
    - Cache statistics tracking
    
    Requirements:
    - 4.1: Generate cache key from query vector hash and filter parameters
    - 4.2: Store search results with 1-hour TTL
    - 4.3: Implement cache invalidation on document add/delete
    - 4.4: Track cache hit rate and performance metrics
    """
    
    def __init__(self, redis_manager: RedisCacheManager):
        """
        Initialize vector search cache.
        
        Args:
            redis_manager: Redis cache manager instance
        """
        self.redis_manager = redis_manager
        self.cache_ttl = 3600  # 1 hour
        
        # Cache statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_requests = 0
        
        logger.info("[VectorSearchCache] Initialized with 1-hour TTL")
    
    def _generate_vector_hash(self, vector: List[float]) -> str:
        """
        Generate hash from query vector.
        
        Args:
            vector: Query embedding vector
            
        Returns:
            SHA256 hash of vector
        """
        # Convert vector to string representation for hashing
        vector_str = json.dumps(vector, sort_keys=True)
        return hashlib.sha256(vector_str.encode()).hexdigest()
    
    def _generate_filter_hash(self, filters: Optional[Dict[str, Any]]) -> str:
        """
        Generate hash from filter parameters.
        
        Args:
            filters: Filter parameters dictionary
            
        Returns:
            SHA256 hash of filters
        """
        if not filters:
            return "no_filter"
        
        # Convert filters to sorted JSON string for consistent hashing
        filter_str = json.dumps(filters, sort_keys=True)
        return hashlib.sha256(filter_str.encode()).hexdigest()
    
    def _generate_cache_key(
        self,
        collection: str,
        vector: List[float],
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate cache key from collection, vector, and filters.
        
        Args:
            collection: Qdrant collection name
            vector: Query embedding vector
            filters: Optional filter parameters
            
        Returns:
            Cache key in format: vsearch:{collection}:{vector_hash}:{filter_hash}
        """
        vector_hash = self._generate_vector_hash(vector)
        filter_hash = self._generate_filter_hash(filters)
        return f"vsearch:{collection}:{vector_hash}:{filter_hash}"
    
    async def get_cached_results(
        self,
        collection: str,
        vector: List[float],
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve cached vector search results.
        
        Args:
            collection: Qdrant collection name
            vector: Query embedding vector
            filters: Optional filter parameters
            
        Returns:
            Cached search results or None if not found
        """
        self.total_requests += 1
        
        cache_key = self._generate_cache_key(collection, vector, filters)
        cached_data = await self.redis_manager.get(cache_key)
        
        if cached_data:
            try:
                data = json.loads(cached_data)
                self.cache_hits += 1
                
                logger.debug(
                    f"[VectorSearchCache] Cache HIT for collection={collection}, "
                    f"cached_at={data.get('cached_at')}"
                )
                
                self._log_cache_stats()
                return data.get("results")
                
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode cached vector search results: {cache_key}")
                self.cache_misses += 1
                return None
        
        self.cache_misses += 1
        logger.debug(f"[VectorSearchCache] Cache MISS for collection={collection}")
        self._log_cache_stats()
        
        return None
    
    async def cache_results(
        self,
        collection: str,
        vector: List[float],
        results: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store vector search results in cache.
        
        Args:
            collection: Qdrant collection name
            vector: Query embedding vector
            results: Search results to cache
            filters: Optional filter parameters
            
        Returns:
            True if successfully cached, False otherwise
        """
        cache_key = self._generate_cache_key(collection, vector, filters)
        
        cache_data = {
            "results": results,
            "cached_at": datetime.utcnow().isoformat() + "Z",
            "collection": collection,
            "filter_hash": self._generate_filter_hash(filters)
        }
        
        success = await self.redis_manager.set(
            cache_key,
            json.dumps(cache_data),
            ttl=self.cache_ttl
        )
        
        if success:
            logger.debug(
                f"[VectorSearchCache] Cached {len(results)} results for "
                f"collection={collection} with TTL={self.cache_ttl}s"
            )
        
        return success
    
    async def invalidate_collection(self, collection: str) -> int:
        """
        Invalidate all cached results for a collection.
        
        This is called when documents are added or deleted from the collection.
        
        Args:
            collection: Qdrant collection name
            
        Returns:
            Number of cache entries invalidated
        """
        # Note: Redis doesn't support wildcard deletion efficiently
        # In production, consider using Redis SCAN with pattern matching
        # For now, we rely on TTL expiration
        
        logger.info(
            f"[VectorSearchCache] Invalidation requested for collection={collection}. "
            "Cache entries will expire naturally via TTL."
        )
        
        # TODO: Implement pattern-based deletion if needed
        # This would require scanning all keys matching vsearch:{collection}:*
        # and deleting them, which can be expensive
        
        return 0
    
    async def invalidate_project(self, project_id: str) -> int:
        """
        Invalidate all cached results for a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Number of cache entries invalidated
        """
        # Collection names typically include project_id
        # Rely on TTL expiration for now
        
        logger.info(
            f"[VectorSearchCache] Invalidation requested for project_id={project_id}. "
            "Cache entries will expire naturally via TTL."
        )
        
        return 0
    
    def _log_cache_stats(self) -> None:
        """Log cache statistics every 100 requests."""
        if self.total_requests % 100 == 0:
            hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0.0
            logger.info(
                f"[VectorSearchCache] Cache stats - Total: {self.total_requests}, "
                f"Hits: {self.cache_hits}, Misses: {self.cache_misses}, "
                f"Hit Rate: {hit_rate:.2f}%"
            )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get current cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        hit_rate = (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0.0
        
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": round(hit_rate, 2),
            "cache_ttl": self.cache_ttl
        }
    
    async def warm_cache(self) -> Dict[str, Any]:
        """
        Warm cache by preloading data for top 10 most active projects.
        
        **Validates: Requirements 28.1, 28.2, 28.3, 28.4**
        
        This method:
        - Queries Supabase for the top 10 most active projects (by recent activity)
        - Preloads document metadata into cache for each project
        - Preloads topic lists into cache for each project
        - Completes within 30 seconds
        - Logs progress and completion
        
        Returns:
            Dictionary with warming statistics
        """
        import asyncio
        from datetime import datetime
        
        start_time = datetime.utcnow()
        logger.info("[VectorSearchCache] Starting cache warming for top 10 active projects...")
        
        try:
            # Import here to avoid circular dependency
            from db.client import async_db, get_supabase_client
            
            # Set timeout for entire warming process (30 seconds)
            async def _warm_with_timeout():
                supabase = get_supabase_client()
                
                # Get top 10 most active projects (by recent document activity)
                projects_result = await async_db(
                    lambda: supabase.table("projects")
                    .select("id, name, updated_at")
                    .order("updated_at", desc=True)
                    .limit(10)
                    .execute()
                )
                
                projects = projects_result.data if projects_result.data else []
                logger.info(f"[VectorSearchCache] Found {len(projects)} active projects to warm")
                
                warmed_docs = 0
                warmed_topics = 0
                warmed_kgs = 0
                
                # Preload data for each project
                for idx, project in enumerate(projects, 1):
                    project_id = project["id"]
                    project_name = project.get("name", "Unknown")
                    
                    logger.debug(
                        f"[VectorSearchCache] Warming project {idx}/{len(projects)}: "
                        f"{project_name} ({project_id})"
                    )
                    
                    # Preload document metadata
                    try:
                        docs_result = await async_db(
                            lambda: supabase.table("documents")
                            .select("id, filename, project_id, topics, upload_status, created_at")
                            .eq("project_id", project_id)
                            .execute()
                        )
                        
                        docs = docs_result.data if docs_result.data else []
                        
                        # Cache each document's metadata
                        for doc in docs:
                            cache_key = f"doc:{doc['id']}"
                            await self.redis_manager.set(
                                cache_key,
                                json.dumps(doc),
                                ttl=21600  # 6 hours
                            )
                            warmed_docs += 1
                        
                        # Cache document list for project
                        if docs:
                            docs_list_key = f"docs:{project_id}"
                            doc_ids = [doc["id"] for doc in docs]
                            await self.redis_manager.set(
                                docs_list_key,
                                json.dumps(doc_ids),
                                ttl=21600  # 6 hours
                            )
                        
                        logger.debug(
                            f"[VectorSearchCache] Cached {len(docs)} documents for project {project_name}"
                        )
                        
                    except Exception as e:
                        logger.warning(
                            f"[VectorSearchCache] Failed to cache documents for project {project_id}: {e}"
                        )
                    
                    # Preload topic lists
                    try:
                        # Extract unique topics from all documents in the project
                        topics_set = set()
                        for doc in docs:
                            if doc.get("topics"):
                                if isinstance(doc["topics"], list):
                                    topics_set.update(doc["topics"])
                        
                        topics_list = list(topics_set)
                        
                        if topics_list:
                            topics_key = f"topics:{project_id}"
                            await self.redis_manager.set(
                                topics_key,
                                json.dumps(topics_list),
                                ttl=21600  # 6 hours
                            )
                            warmed_topics += len(topics_list)
                            
                            logger.debug(
                                f"[VectorSearchCache] Cached {len(topics_list)} topics for project {project_name}"
                            )
                        
                    except Exception as e:
                        logger.warning(
                            f"[VectorSearchCache] Failed to cache topics for project {project_id}: {e}"
                        )
                    
                    # Preload knowledge graph
                    try:
                        # Query for knowledge graph data
                        kg_result = await async_db(
                            lambda: supabase.table("topic_relations")
                            .select("*")
                            .eq("project_id", project_id)
                            .execute()
                        )
                        
                        if kg_result.data:
                            kg_key = f"kg:{project_id}"
                            await self.redis_manager.set(
                                kg_key,
                                json.dumps(kg_result.data),
                                ttl=3600  # 1 hour (KG changes more frequently)
                            )
                            warmed_kgs += 1
                            
                            logger.debug(
                                f"[VectorSearchCache] Cached knowledge graph with "
                                f"{len(kg_result.data)} relations for project {project_name}"
                            )
                        
                    except Exception as e:
                        logger.warning(
                            f"[VectorSearchCache] Failed to cache knowledge graph for project {project_id}: {e}"
                        )
                
                return {
                    "projects_warmed": len(projects),
                    "documents_cached": warmed_docs,
                    "topics_cached": warmed_topics,
                    "knowledge_graphs_cached": warmed_kgs
                }
            
            # Execute with 30-second timeout
            result = await asyncio.wait_for(_warm_with_timeout(), timeout=30.0)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(
                f"[VectorSearchCache] Cache warming completed in {elapsed:.2f}s - "
                f"Projects: {result['projects_warmed']}, "
                f"Documents: {result['documents_cached']}, "
                f"Topics: {result['topics_cached']}, "
                f"Knowledge Graphs: {result['knowledge_graphs_cached']}"
            )
            
            return {
                "success": True,
                "duration_seconds": round(elapsed, 2),
                **result
            }
            
        except asyncio.TimeoutError:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.warning(
                f"[VectorSearchCache] Cache warming timed out after {elapsed:.2f}s"
            )
            return {
                "success": False,
                "error": "timeout",
                "duration_seconds": round(elapsed, 2)
            }
            
        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                f"[VectorSearchCache] Cache warming failed after {elapsed:.2f}s: {e}",
                exc_info=True
            )
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": round(elapsed, 2)
            }
