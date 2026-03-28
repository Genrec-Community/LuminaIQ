"""Unit tests for DistributedLockManager.

**Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from core.lock_manager import DistributedLockManager
from core.redis_manager import RedisCacheManager


@pytest.fixture
async def redis_manager():
    """Create a mock RedisCacheManager for testing."""
    manager = MagicMock(spec=RedisCacheManager)
    manager.is_available = True
    manager.set = AsyncMock(return_value=True)
    manager.get = AsyncMock(return_value=None)
    manager.delete = AsyncMock(return_value=True)
    manager.expire = AsyncMock(return_value=True)
    manager.exists = AsyncMock(return_value=False)
    return manager


@pytest.fixture
async def lock_manager(redis_manager):
    """Create a DistributedLockManager instance for testing."""
    return DistributedLockManager(redis_manager)


@pytest.mark.asyncio
async def test_initialization(redis_manager):
    """Test DistributedLockManager initialization."""
    manager = DistributedLockManager(redis_manager)
    
    assert manager.redis_manager == redis_manager
    assert manager.default_ttl == 300  # 5 minutes
    assert manager.default_timeout == 5  # 5 seconds


@pytest.mark.asyncio
async def test_acquire_lock_success(lock_manager, redis_manager):
    """Test successful lock acquisition."""
    resource_id = "kg_build:proj_123"
    
    # Mock successful lock acquisition
    # The lock manager checks if the value matches the token after setting
    lock_token_holder = []
    
    async def set_side_effect(key, value, ttl=None):
        lock_token_holder.append(value)
        return True
    
    async def get_side_effect(key):
        if lock_token_holder:
            return lock_token_holder[0]
        return None
    
    redis_manager.set = AsyncMock(side_effect=set_side_effect)
    redis_manager.get = AsyncMock(side_effect=get_side_effect)
    
    lock_token = await lock_manager.acquire_lock(resource_id, timeout=1, ttl=300)
    
    assert lock_token is not None
    assert isinstance(lock_token, str)
    assert len(lock_token) > 0
    
    # Verify Redis set was called with correct parameters
    redis_manager.set.assert_called()
    call_args = redis_manager.set.call_args
    assert call_args[0][0] == f"lock:{resource_id}"
    assert call_args[1]["ttl"] == 300


@pytest.mark.asyncio
async def test_acquire_lock_timeout(lock_manager, redis_manager):
    """Test lock acquisition timeout (Requirement 12.3)."""
    resource_id = "kg_build:proj_123"
    
    # Mock lock already held by another process
    redis_manager.set.return_value = True
    redis_manager.get.return_value = "other-token"  # Different token
    
    lock_token = await lock_manager.acquire_lock(resource_id, timeout=1, ttl=300)
    
    # Should timeout and return None
    assert lock_token is None


@pytest.mark.asyncio
async def test_acquire_lock_redis_unavailable(lock_manager, redis_manager):
    """Test lock acquisition when Redis is unavailable."""
    resource_id = "kg_build:proj_123"
    redis_manager.is_available = False
    
    lock_token = await lock_manager.acquire_lock(resource_id)
    
    assert lock_token is None


@pytest.mark.asyncio
async def test_release_lock_success(lock_manager, redis_manager):
    """Test successful lock release."""
    resource_id = "kg_build:proj_123"
    lock_token = "test-token-123"
    
    # Mock that we own the lock
    redis_manager.get.return_value = lock_token
    redis_manager.delete.return_value = True
    
    success = await lock_manager.release_lock(resource_id, lock_token)
    
    assert success
    
    # Verify Redis delete was called
    redis_manager.delete.assert_called_once_with(f"lock:{resource_id}")


@pytest.mark.asyncio
async def test_release_lock_token_mismatch(lock_manager, redis_manager):
    """Test lock release with wrong token."""
    resource_id = "kg_build:proj_123"
    our_token = "our-token"
    other_token = "other-token"
    
    # Mock that someone else owns the lock
    redis_manager.get.return_value = other_token
    
    success = await lock_manager.release_lock(resource_id, our_token)
    
    assert not success
    
    # Verify Redis delete was NOT called
    redis_manager.delete.assert_not_called()


@pytest.mark.asyncio
async def test_release_lock_not_held(lock_manager, redis_manager):
    """Test releasing a lock that isn't held."""
    resource_id = "kg_build:proj_123"
    lock_token = "test-token"
    
    # Mock that lock doesn't exist
    redis_manager.get.return_value = None
    
    success = await lock_manager.release_lock(resource_id, lock_token)
    
    assert not success


@pytest.mark.asyncio
async def test_extend_lock_success(lock_manager, redis_manager):
    """Test successful lock extension."""
    resource_id = "kg_build:proj_123"
    lock_token = "test-token-123"
    
    # Mock that we own the lock
    redis_manager.get.return_value = lock_token
    redis_manager.expire.return_value = True
    
    success = await lock_manager.extend_lock(resource_id, lock_token, ttl=600)
    
    assert success
    
    # Verify Redis expire was called
    redis_manager.expire.assert_called_once_with(f"lock:{resource_id}", 600)


@pytest.mark.asyncio
async def test_extend_lock_token_mismatch(lock_manager, redis_manager):
    """Test lock extension with wrong token."""
    resource_id = "kg_build:proj_123"
    our_token = "our-token"
    other_token = "other-token"
    
    # Mock that someone else owns the lock
    redis_manager.get.return_value = other_token
    
    success = await lock_manager.extend_lock(resource_id, our_token)
    
    assert not success
    
    # Verify Redis expire was NOT called
    redis_manager.expire.assert_not_called()


@pytest.mark.asyncio
async def test_lock_context_manager_success(lock_manager, redis_manager):
    """Test lock context manager for automatic release."""
    resource_id = "kg_build:proj_123"
    
    # Mock successful lock acquisition
    lock_token_holder = []
    
    async def set_side_effect(key, value, ttl=None):
        lock_token_holder.append(value)
        return True
    
    async def get_side_effect(key):
        if lock_token_holder:
            return lock_token_holder[0]
        return None
    
    redis_manager.set = AsyncMock(side_effect=set_side_effect)
    redis_manager.get = AsyncMock(side_effect=get_side_effect)
    redis_manager.delete.return_value = True
    
    # Use context manager
    async with lock_manager.lock(resource_id, timeout=1, ttl=300) as token:
        assert token is not None
        assert isinstance(token, str)
    
    # Verify lock was released
    redis_manager.delete.assert_called_once()


@pytest.mark.asyncio
async def test_lock_context_manager_timeout(lock_manager, redis_manager):
    """Test lock context manager timeout."""
    resource_id = "kg_build:proj_123"
    
    # Mock lock already held
    redis_manager.set.return_value = True
    redis_manager.get.return_value = "other-token"
    
    # Should raise RuntimeError on timeout
    with pytest.raises(RuntimeError, match="Failed to acquire lock"):
        async with lock_manager.lock(resource_id, timeout=1):
            pass


@pytest.mark.asyncio
async def test_lock_context_manager_exception_handling(lock_manager, redis_manager):
    """Test that lock is released even if exception occurs."""
    resource_id = "kg_build:proj_123"
    
    # Mock successful lock acquisition
    lock_token_holder = []
    
    async def set_side_effect(key, value, ttl=None):
        lock_token_holder.append(value)
        return True
    
    async def get_side_effect(key):
        if lock_token_holder:
            return lock_token_holder[0]
        return None
    
    redis_manager.set = AsyncMock(side_effect=set_side_effect)
    redis_manager.get = AsyncMock(side_effect=get_side_effect)
    redis_manager.delete.return_value = True
    
    # Use context manager with exception
    try:
        async with lock_manager.lock(resource_id, timeout=1):
            raise ValueError("Test exception")
    except ValueError:
        pass
    
    # Verify lock was still released
    redis_manager.delete.assert_called_once()


@pytest.mark.asyncio
async def test_is_locked(lock_manager, redis_manager):
    """Test checking if resource is locked."""
    resource_id = "kg_build:proj_123"
    
    # Mock lock exists
    redis_manager.exists.return_value = True
    
    is_locked = await lock_manager.is_locked(resource_id)
    
    assert is_locked
    redis_manager.exists.assert_called_once_with(f"lock:{resource_id}")


@pytest.mark.asyncio
async def test_is_not_locked(lock_manager, redis_manager):
    """Test checking if resource is not locked."""
    resource_id = "kg_build:proj_123"
    
    # Mock lock doesn't exist
    redis_manager.exists.return_value = False
    
    is_locked = await lock_manager.is_locked(resource_id)
    
    assert not is_locked


@pytest.mark.asyncio
async def test_get_lock_info(lock_manager, redis_manager):
    """Test getting lock information."""
    resource_id = "kg_build:proj_123"
    lock_token = "test-token-123"
    
    # Mock lock exists
    redis_manager.get.return_value = lock_token
    
    lock_info = await lock_manager.get_lock_info(resource_id)
    
    assert lock_info is not None
    assert lock_info["resource_id"] == resource_id
    assert lock_info["lock_token"] == lock_token
    assert lock_info["is_locked"] is True


@pytest.mark.asyncio
async def test_get_lock_info_not_locked(lock_manager, redis_manager):
    """Test getting lock info when not locked."""
    resource_id = "kg_build:proj_123"
    
    # Mock lock doesn't exist
    redis_manager.get.return_value = None
    
    lock_info = await lock_manager.get_lock_info(resource_id)
    
    assert lock_info is None


@pytest.mark.asyncio
async def test_lock_auto_expiration(lock_manager):
    """Test that locks have automatic expiration (Requirement 12.5)."""
    # Default TTL should be 5 minutes (300 seconds)
    assert lock_manager.default_ttl == 300


@pytest.mark.asyncio
async def test_lock_key_format(lock_manager):
    """Test lock key format."""
    resource_id = "kg_build:proj_123"
    
    lock_key = lock_manager._generate_lock_key(resource_id)
    
    assert lock_key == f"lock:{resource_id}"


@pytest.mark.asyncio
async def test_concurrent_lock_attempts(lock_manager, redis_manager):
    """Test concurrent lock acquisition attempts (Requirement 12.2)."""
    resource_id = "kg_build:proj_123"
    
    # First acquisition succeeds
    lock_token_holder = []
    
    async def set_side_effect(key, value, ttl=None):
        if not lock_token_holder:  # Only first call succeeds
            lock_token_holder.append(value)
            return True
        return True  # Subsequent calls also return True but lock is held
    
    async def get_side_effect(key):
        if lock_token_holder:
            return lock_token_holder[0]  # Always return first token
        return None
    
    redis_manager.set = AsyncMock(side_effect=set_side_effect)
    redis_manager.get = AsyncMock(side_effect=get_side_effect)
    
    # First caller acquires lock
    token1 = await lock_manager.acquire_lock(resource_id, timeout=1)
    assert token1 is not None
    
    # Second caller should timeout (lock held by different token)
    token2 = await lock_manager.acquire_lock(resource_id, timeout=1)
    assert token2 is None


@pytest.mark.asyncio
async def test_lock_timeout_5_seconds(lock_manager):
    """Test default lock acquisition timeout is 5 seconds (Requirement 12.3)."""
    assert lock_manager.default_timeout == 5
