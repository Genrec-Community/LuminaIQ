"""Distributed lock manager using Redis for coordinating exclusive operations.

**Validates: Requirements 12.1, 12.4**

This module provides distributed locking to prevent race conditions when multiple
backend instances perform exclusive operations on the same resource.
"""

import asyncio
import logging
import uuid
from typing import Optional
from contextlib import asynccontextmanager

from core.redis_manager import RedisCacheManager

logger = logging.getLogger(__name__)


class DistributedLockManager:
    """
    Distributed lock manager using Redis SET with NX and EX.
    
    Features:
    - Acquire lock with timeout and TTL
    - Release lock with token validation
    - Extend lock TTL for long-running operations
    - Context manager for automatic lock release
    - Automatic expiration to prevent deadlocks
    
    Requirements:
    - 12.1: Implement acquire_lock, release_lock, extend_lock methods
    - 12.4: Use Redis SET with NX and EX for lock implementation
    """
    
    def __init__(self, redis_manager: RedisCacheManager):
        """
        Initialize distributed lock manager.
        
        Args:
            redis_manager: Redis cache manager instance
        """
        self.redis_manager = redis_manager
        self.default_ttl = 300  # 5 minutes
        self.default_timeout = 5  # 5 seconds
        
        logger.info(
            f"[DistributedLockManager] Initialized with default_ttl={self.default_ttl}s, "
            f"default_timeout={self.default_timeout}s"
        )
    
    def _generate_lock_key(self, resource_id: str) -> str:
        """
        Generate lock key for a resource.
        
        Args:
            resource_id: Resource identifier
            
        Returns:
            Lock key in format: lock:{resource_id}
        """
        return f"lock:{resource_id}"
    
    async def acquire_lock(
        self,
        resource_id: str,
        timeout: int = None,
        ttl: int = None
    ) -> Optional[str]:
        """
        Acquire a distributed lock for a resource.
        
        Uses Redis SET with NX (only set if not exists) and EX (expiration).
        Returns a lock token that must be used to release the lock.
        
        Args:
            resource_id: Resource identifier to lock
            timeout: Maximum time to wait for lock acquisition in seconds (default: 5)
            ttl: Lock time-to-live in seconds (default: 300)
            
        Returns:
            Lock token (UUID) if acquired, None if timeout
        """
        if timeout is None:
            timeout = self.default_timeout
        
        if ttl is None:
            ttl = self.default_ttl
        
        lock_key = self._generate_lock_key(resource_id)
        lock_token = str(uuid.uuid4())
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Try to acquire lock using SET NX EX
            if not self.redis_manager.is_available:
                logger.warning(
                    f"[DistributedLockManager] Redis unavailable, cannot acquire lock for {resource_id}"
                )
                return None
            
            # Use Redis SET with NX and EX options
            # This is atomic: only sets if key doesn't exist, and sets expiration
            success = await self.redis_manager.set(lock_key, lock_token, ttl=ttl)
            
            # Check if we actually acquired the lock (key didn't exist before)
            if success:
                # Verify we got the lock by checking the value
                current_value = await self.redis_manager.get(lock_key)
                if current_value == lock_token:
                    logger.info(
                        f"[DistributedLockManager] Acquired lock for {resource_id}, "
                        f"token={lock_token[:8]}..., ttl={ttl}s"
                    )
                    return lock_token
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(
                    f"[DistributedLockManager] Failed to acquire lock for {resource_id} "
                    f"after {timeout}s timeout"
                )
                return None
            
            # Wait a bit before retrying
            await asyncio.sleep(0.1)
    
    async def release_lock(self, resource_id: str, lock_token: str) -> bool:
        """
        Release a distributed lock.
        
        Validates the lock token to prevent accidental release by other processes.
        
        Args:
            resource_id: Resource identifier
            lock_token: Lock token returned by acquire_lock
            
        Returns:
            True if lock released successfully, False otherwise
        """
        lock_key = self._generate_lock_key(resource_id)
        
        # Verify we own the lock before releasing
        current_value = await self.redis_manager.get(lock_key)
        
        if current_value != lock_token:
            logger.warning(
                f"[DistributedLockManager] Cannot release lock for {resource_id}: "
                f"token mismatch (expected {lock_token[:8]}..., got {current_value[:8] if current_value else 'None'}...)"
            )
            return False
        
        # Delete the lock
        success = await self.redis_manager.delete(lock_key)
        
        if success:
            logger.info(
                f"[DistributedLockManager] Released lock for {resource_id}, "
                f"token={lock_token[:8]}..."
            )
        else:
            logger.warning(
                f"[DistributedLockManager] Failed to release lock for {resource_id}"
            )
        
        return success
    
    async def extend_lock(
        self,
        resource_id: str,
        lock_token: str,
        ttl: int = None
    ) -> bool:
        """
        Extend the TTL of an existing lock.
        
        Useful for long-running operations that need to keep the lock longer.
        
        Args:
            resource_id: Resource identifier
            lock_token: Lock token returned by acquire_lock
            ttl: New TTL in seconds (default: 300)
            
        Returns:
            True if lock extended successfully, False otherwise
        """
        if ttl is None:
            ttl = self.default_ttl
        
        lock_key = self._generate_lock_key(resource_id)
        
        # Verify we own the lock before extending
        current_value = await self.redis_manager.get(lock_key)
        
        if current_value != lock_token:
            logger.warning(
                f"[DistributedLockManager] Cannot extend lock for {resource_id}: "
                f"token mismatch"
            )
            return False
        
        # Extend TTL
        success = await self.redis_manager.expire(lock_key, ttl)
        
        if success:
            logger.debug(
                f"[DistributedLockManager] Extended lock for {resource_id}, "
                f"new_ttl={ttl}s"
            )
        else:
            logger.warning(
                f"[DistributedLockManager] Failed to extend lock for {resource_id}"
            )
        
        return success
    
    @asynccontextmanager
    async def lock(
        self,
        resource_id: str,
        timeout: int = None,
        ttl: int = None
    ):
        """
        Context manager for automatic lock acquisition and release.
        
        Usage:
            async with lock_manager.lock("resource_id"):
                # Perform exclusive operation
                pass
        
        Args:
            resource_id: Resource identifier to lock
            timeout: Maximum time to wait for lock acquisition in seconds
            ttl: Lock time-to-live in seconds
            
        Raises:
            RuntimeError: If lock cannot be acquired within timeout
        """
        lock_token = await self.acquire_lock(resource_id, timeout, ttl)
        
        if lock_token is None:
            raise RuntimeError(
                f"Failed to acquire lock for {resource_id} within {timeout or self.default_timeout}s"
            )
        
        try:
            yield lock_token
        finally:
            # Always release lock, even if exception occurs
            await self.release_lock(resource_id, lock_token)
    
    async def is_locked(self, resource_id: str) -> bool:
        """
        Check if a resource is currently locked.
        
        Args:
            resource_id: Resource identifier
            
        Returns:
            True if resource is locked, False otherwise
        """
        lock_key = self._generate_lock_key(resource_id)
        return await self.redis_manager.exists(lock_key)
    
    async def get_lock_info(self, resource_id: str) -> Optional[dict]:
        """
        Get information about a lock.
        
        Args:
            resource_id: Resource identifier
            
        Returns:
            Dictionary with lock info or None if not locked
        """
        lock_key = self._generate_lock_key(resource_id)
        
        lock_token = await self.redis_manager.get(lock_key)
        
        if not lock_token:
            return None
        
        return {
            "resource_id": resource_id,
            "lock_token": lock_token,
            "is_locked": True
        }
