"""
Caching utilities for fast data access.

Provides in-memory caching for frequently accessed data:
- User profiles
- Learning paths
- Generated content
- Project metadata

For production, use Redis. This provides in-memory caching with TTL.
"""

import time
import hashlib
import json
from typing import Any, Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached item"""
    value: Any
    expires_at: float
    created_at: float


class MemoryCache:
    """
    Simple in-memory cache with TTL.
    Thread-safe for async operations.
    """
    
    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
        
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from arguments"""
        key_parts = [prefix]
        for arg in args:
            if arg is not None:
                key_parts.append(str(arg))
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={v}")
        key_str = ":".join(key_parts)
        # Hash long keys
        if len(key_str) > 200:
            return hashlib.md5(key_str.encode()).hexdigest()
        return key_str
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if time.time() > entry.expires_at:
                del self._cache[key]
                return None
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        ttl = ttl or self._default_ttl
        async with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl,
                created_at=time.time()
            )
    
    async def delete(self, key: str) -> None:
        """Delete a key from cache"""
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear_prefix(self, prefix: str) -> int:
        """Clear all keys starting with prefix"""
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    def get_sync(self, key: str) -> Optional[Any]:
        """Synchronous get (for non-async contexts)"""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            return None
        return entry.value
    
    def set_sync(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Synchronous set"""
        ttl = ttl or self._default_ttl
        self._cache[key] = CacheEntry(
            value=value,
            expires_at=time.time() + ttl,
            created_at=time.time()
        )
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries"""
        now = time.time()
        async with self._lock:
            expired_keys = [
                k for k, v in self._cache.items() 
                if now > v.expires_at
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


# Cache instances for different data types
user_cache = MemoryCache(default_ttl=600)  # 10 min for user data
project_cache = MemoryCache(default_ttl=300)  # 5 min for project data
learning_cache = MemoryCache(default_ttl=1800)  # 30 min for learning paths
content_cache = MemoryCache(default_ttl=3600)  # 1 hour for generated content


# Decorator for caching async functions
def cached(cache: MemoryCache, ttl: Optional[int] = None, key_prefix: str = ""):
    """Decorator to cache async function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache._make_key(key_prefix or func.__name__, *args, **kwargs)
            
            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            logger.debug(f"Cache miss (set): {cache_key}")
            return result
        return wrapper
    return decorator


# Cache key generators
def user_key(user_id: str) -> str:
    return f"user:{user_id}"

def user_profile_key(user_id: str) -> str:
    return f"user_profile:{user_id}"

def project_key(project_id: str) -> str:
    return f"project:{project_id}"

def project_summary_key(project_id: str) -> str:
    return f"project_summary:{project_id}"

def learning_path_key(user_id: str, project_id: str) -> str:
    return f"learning_path:{user_id}:{project_id}"

def topics_key(project_id: str) -> str:
    return f"topics:{project_id}"


# Invalidate cache helpers
async def invalidate_user_cache(user_id: str):
    """Invalidate all cache entries for a user"""
    await user_cache.delete(user_key(user_id))
    await user_cache.delete(user_profile_key(user_id))
    await learning_cache.clear_prefix(f"learning_path:{user_id}:")

async def invalidate_project_cache(project_id: str):
    """Invalidate all cache entries for a project"""
    await project_cache.delete(project_key(project_id))
    await project_cache.delete(project_summary_key(project_id))
    await content_cache.clear_prefix(f"content:{project_id}:")


# Background cleanup task
async def start_cache_cleanup():
    """Start periodic cache cleanup"""
    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            total_cleaned = 0
            total_cleaned += await user_cache.cleanup_expired()
            total_cleaned += await project_cache.cleanup_expired()
            total_cleaned += await learning_cache.cleanup_expired()
            total_cleaned += await content_cache.cleanup_expired()
            if total_cleaned > 0:
                logger.info(f"Cache cleanup: removed {total_cleaned} expired entries")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
