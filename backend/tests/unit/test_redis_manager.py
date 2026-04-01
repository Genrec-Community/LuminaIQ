"""Unit tests for RedisCacheManager."""

import pytest

from core.redis_manager import RedisCacheManager


@pytest.fixture
async def redis_manager():
    """Create a RedisCacheManager instance for testing."""
    manager = RedisCacheManager(
        host="localhost",
        port=6379,
        password="",
        db=0,
        max_connections=50,
    )
    yield manager
    await manager.disconnect()


@pytest.mark.asyncio
async def test_initialization():
    """Test RedisCacheManager initialization."""
    manager = RedisCacheManager(
        host="localhost",
        port=6379,
        password="test_password",
        db=1,
        max_connections=30,
    )
    
    assert manager.host == "localhost"
    assert manager.port == 6379
    assert manager.password == "test_password"
    assert manager.db == 1
    assert manager.max_connections == 30
    assert not manager.is_available


@pytest.mark.asyncio
async def test_graceful_degradation_on_connection_failure():
    """Test that manager handles connection failures gracefully."""
    manager = RedisCacheManager(
        host="invalid-host",
        port=9999,
        password="",
        db=0,
        retry_attempts=1,
    )
    
    # Should not raise exception, just log warning
    await manager.connect()
    
    # Should be marked as unavailable
    assert not manager.is_available
    
    # Operations should return None/False without raising exceptions
    result = await manager.get("test_key")
    assert result is None
    
    success = await manager.set("test_key", "test_value")
    assert not success


@pytest.mark.asyncio
async def test_get_returns_none_when_unavailable(redis_manager):
    """Test that get returns None when Redis is unavailable."""
    redis_manager._is_available = False
    
    result = await redis_manager.get("test_key")
    assert result is None


@pytest.mark.asyncio
async def test_set_returns_false_when_unavailable(redis_manager):
    """Test that set returns False when Redis is unavailable."""
    redis_manager._is_available = False
    
    result = await redis_manager.set("test_key", "test_value")
    assert not result


@pytest.mark.asyncio
async def test_get_stats():
    """Test cache statistics tracking."""
    manager = RedisCacheManager(
        host="localhost",
        port=6379,
        password="",
        db=0,
    )
    
    # Initial stats
    stats = manager.get_stats()
    assert stats["hit_rate"] == 0.0
    assert stats["miss_rate"] == 0.0
    assert stats["total_requests"] == 0
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["errors"] == 0
    assert not stats["is_available"]


@pytest.mark.asyncio
async def test_exists_returns_false_when_unavailable(redis_manager):
    """Test that exists returns False when Redis is unavailable."""
    redis_manager._is_available = False
    
    result = await redis_manager.exists("test_key")
    assert not result


@pytest.mark.asyncio
async def test_delete_returns_false_when_unavailable(redis_manager):
    """Test that delete returns False when Redis is unavailable."""
    redis_manager._is_available = False
    
    result = await redis_manager.delete("test_key")
    assert not result


@pytest.mark.asyncio
async def test_get_many_returns_empty_dict_when_unavailable(redis_manager):
    """Test that get_many returns empty dict when Redis is unavailable."""
    redis_manager._is_available = False
    
    result = await redis_manager.get_many(["key1", "key2", "key3"])
    assert result == {}


@pytest.mark.asyncio
async def test_set_many_returns_false_when_unavailable(redis_manager):
    """Test that set_many returns False when Redis is unavailable."""
    redis_manager._is_available = False
    
    result = await redis_manager.set_many({"key1": "value1", "key2": "value2"})
    assert not result


@pytest.mark.asyncio
async def test_increment_returns_zero_when_unavailable(redis_manager):
    """Test that increment returns 0 when Redis is unavailable."""
    redis_manager._is_available = False
    
    result = await redis_manager.increment("counter")
    assert result == 0


@pytest.mark.asyncio
async def test_expire_returns_false_when_unavailable(redis_manager):
    """Test that expire returns False when Redis is unavailable."""
    redis_manager._is_available = False
    
    result = await redis_manager.expire("test_key", 60)
    assert not result


@pytest.mark.asyncio
async def test_connection_pool_configuration():
    """Test that connection pool is configured correctly."""
    manager = RedisCacheManager(
        host="localhost",
        port=6379,
        password="test_pass",
        db=2,
        max_connections=75,
        socket_timeout=10,
        socket_connect_timeout=8,
    )
    
    assert manager.max_connections == 75
    assert manager.socket_timeout == 10
    assert manager.socket_connect_timeout == 8
