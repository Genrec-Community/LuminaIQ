"""Integration test for Redis Cache Manager."""

import pytest
from core.redis_manager import RedisCacheManager


@pytest.mark.asyncio
@pytest.mark.integration
async def test_redis_integration():
    """Test Redis manager with actual Redis connection."""
    print("\nTesting Redis Cache Manager Integration...")
    
    # Initialize manager
    manager = RedisCacheManager(
        host="localhost",
        port=6379,
        password="",
        db=0,
        max_connections=50,
        retry_attempts=1,  # Quick fail for testing
    )
    
    print("✓ Manager initialized")
    
    # Connect to Redis
    await manager.connect()
    
    if not manager.is_available:
        print("⚠ Redis not available - testing graceful degradation")
        
        # Test graceful degradation
        result = await manager.get("test_key")
        assert result is None, "get() should return None when unavailable"
        
        success = await manager.set("test_key", "test_value")
        assert not success, "set() should return False when unavailable"
        
        print("✓ Graceful degradation working correctly")
        pytest.skip("Redis not available - skipping integration tests")
        return
    
    print(f"✓ Connected to Redis at {manager.host}:{manager.port}")
    
    # Test basic operations
    test_key = "test:integration:key"
    test_value = "Hello Redis!"
    
    # Set value
    success = await manager.set(test_key, test_value, ttl=60)
    assert success, "Failed to set value"
    print(f"✓ Set key: {test_key}")
    
    # Get value
    result = await manager.get(test_key)
    assert result == test_value, f"Expected {test_value}, got {result}"
    print(f"✓ Get key: {test_key} = {result}")
    
    # Check exists
    exists = await manager.exists(test_key)
    assert exists, "Key should exist"
    print(f"✓ Key exists: {test_key}")
    
    # Test batch operations
    batch_items = {
        "test:batch:1": "value1",
        "test:batch:2": "value2",
        "test:batch:3": "value3",
    }
    
    success = await manager.set_many(batch_items, ttl=60)
    assert success, "Failed to set batch"
    print(f"✓ Set batch: {len(batch_items)} keys")
    
    batch_results = await manager.get_many(list(batch_items.keys()))
    assert len(batch_results) == len(batch_items), "Batch get failed"
    print(f"✓ Get batch: {len(batch_results)} keys retrieved")
    
    # Test increment
    counter_key = "test:counter"
    count = await manager.increment(counter_key)
    assert count > 0, "Increment failed"
    print(f"✓ Increment counter: {count}")
    
    # Test delete
    success = await manager.delete(test_key)
    assert success, "Failed to delete key"
    print(f"✓ Deleted key: {test_key}")
    
    # Verify deletion
    result = await manager.get(test_key)
    assert result is None, "Key should be deleted"
    print("✓ Verified deletion")
    
    # Get stats
    stats = manager.get_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"   Total Requests: {stats['total_requests']}")
    print(f"   Hits: {stats['hits']}")
    print(f"   Misses: {stats['misses']}")
    print(f"   Hit Rate: {stats['hit_rate']}%")
    print(f"   Errors: {stats['errors']}")
    print(f"   Available: {stats['is_available']}")
    
    # Cleanup
    await manager.delete(counter_key)
    for key in batch_items.keys():
        await manager.delete(key)
    
    # Disconnect
    await manager.disconnect()
    print("\n✓ Disconnected from Redis")
    
    print("\n✅ All integration tests passed!")
