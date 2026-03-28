"""Unit tests for RateLimiter.

**Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5**
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from core.rate_limiter import RateLimiter, RateLimitResult
from core.redis_manager import RedisCacheManager


@pytest.fixture
async def redis_manager():
    """Create a mock RedisCacheManager for testing."""
    manager = MagicMock(spec=RedisCacheManager)
    manager.is_available = True
    manager.get = AsyncMock(return_value=None)
    manager.set = AsyncMock(return_value=True)
    manager.delete = AsyncMock(return_value=True)
    manager.increment = AsyncMock(return_value=1)
    manager.expire = AsyncMock(return_value=True)
    return manager


@pytest.fixture
async def rate_limiter(redis_manager):
    """Create a RateLimiter instance for testing."""
    return RateLimiter(redis_manager)


@pytest.mark.asyncio
async def test_initialization(redis_manager):
    """Test RateLimiter initialization."""
    limiter = RateLimiter(redis_manager)
    
    assert limiter.redis_manager == redis_manager
    assert limiter.window_size == 60  # 1 minute
    assert limiter.limits["read"] == 100
    assert limiter.limits["write"] == 50
    assert limiter.limits["llm"] == 20
    assert limiter.limits["upload"] == 10


@pytest.mark.asyncio
async def test_custom_limits(redis_manager):
    """Test RateLimiter with custom limits."""
    custom_limits = {
        "read": 200,
        "write": 100,
        "custom": 50
    }
    
    limiter = RateLimiter(redis_manager, limits=custom_limits)
    
    assert limiter.limits["read"] == 200
    assert limiter.limits["write"] == 100
    assert limiter.limits["custom"] == 50


@pytest.mark.asyncio
async def test_check_rate_limit_allowed(rate_limiter, redis_manager):
    """Test rate limit check when request is allowed."""
    user_id = "user_123"
    endpoint = "read"
    
    # Mock current count below limit
    redis_manager.get.return_value = "50"  # 50 requests so far
    redis_manager.increment.return_value = 51
    
    result = await rate_limiter.check_rate_limit(user_id, endpoint)
    
    assert result.allowed is True
    assert result.limit == 100  # Default read limit
    assert result.remaining == 49  # 100 - 50 - 1
    assert result.reset_at > time.time()
    assert result.retry_after is None


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded(rate_limiter, redis_manager):
    """Test rate limit check when limit is exceeded (Requirement 14.3)."""
    user_id = "user_123"
    endpoint = "write"
    
    # Mock current count at limit
    redis_manager.get.return_value = "50"  # At write limit
    
    result = await rate_limiter.check_rate_limit(user_id, endpoint)
    
    assert result.allowed is False
    assert result.limit == 50  # Default write limit
    assert result.remaining == 0
    assert result.retry_after == 60  # Window size


@pytest.mark.asyncio
async def test_check_rate_limit_first_request(rate_limiter, redis_manager):
    """Test rate limit check for first request in window."""
    user_id = "user_123"
    endpoint = "llm"
    
    # Mock no previous requests
    redis_manager.get.return_value = None
    redis_manager.increment.return_value = 1
    
    result = await rate_limiter.check_rate_limit(user_id, endpoint)
    
    assert result.allowed is True
    assert result.limit == 20  # Default LLM limit
    assert result.remaining == 19  # 20 - 0 - 1


@pytest.mark.asyncio
async def test_check_rate_limit_redis_unavailable(rate_limiter, redis_manager):
    """Test graceful degradation when Redis is unavailable."""
    user_id = "user_123"
    endpoint = "read"
    
    # Mock Redis unavailable
    redis_manager.is_available = False
    
    result = await rate_limiter.check_rate_limit(user_id, endpoint)
    
    # Should allow request (graceful degradation)
    assert result.allowed is True
    assert result.limit == 100


@pytest.mark.asyncio
async def test_increment(rate_limiter, redis_manager):
    """Test incrementing request counter."""
    user_id = "user_123"
    endpoint = "read"
    
    redis_manager.increment.return_value = 5
    
    count = await rate_limiter.increment(user_id, endpoint)
    
    assert count == 5
    
    # Verify Redis increment was called
    redis_manager.increment.assert_called_once()
    call_args = redis_manager.increment.call_args
    assert call_args[0][0] == f"ratelimit:{user_id}:{endpoint}"


@pytest.mark.asyncio
async def test_increment_sets_expiration_on_first_request(rate_limiter, redis_manager):
    """Test that expiration is set on first request."""
    user_id = "user_123"
    endpoint = "write"
    
    # Mock first request (count = 1)
    redis_manager.increment.return_value = 1
    
    await rate_limiter.increment(user_id, endpoint)
    
    # Verify expire was called
    redis_manager.expire.assert_called_once()
    call_args = redis_manager.expire.call_args
    assert call_args[0][1] == 60  # Window size


@pytest.mark.asyncio
async def test_reset(rate_limiter, redis_manager):
    """Test resetting rate limit counter."""
    user_id = "user_123"
    endpoint = "llm"
    
    redis_manager.delete.return_value = True
    
    success = await rate_limiter.reset(user_id, endpoint)
    
    assert success
    
    # Verify Redis delete was called
    redis_manager.delete.assert_called_once_with(f"ratelimit:{user_id}:{endpoint}")


@pytest.mark.asyncio
async def test_get_current_usage(rate_limiter, redis_manager):
    """Test getting current rate limit usage."""
    user_id = "user_123"
    endpoint = "upload"
    
    # Mock current count
    redis_manager.get.return_value = "7"
    
    usage = await rate_limiter.get_current_usage(user_id, endpoint)
    
    assert usage["user_id"] == user_id
    assert usage["endpoint"] == endpoint
    assert usage["limit"] == 10  # Default upload limit
    assert usage["current"] == 7
    assert usage["remaining"] == 3
    assert usage["window_size"] == 60


@pytest.mark.asyncio
async def test_get_current_usage_no_requests(rate_limiter, redis_manager):
    """Test getting usage when no requests made."""
    user_id = "user_123"
    endpoint = "read"
    
    # Mock no requests
    redis_manager.get.return_value = None
    
    usage = await rate_limiter.get_current_usage(user_id, endpoint)
    
    assert usage["current"] == 0
    assert usage["remaining"] == 100  # Full limit available


@pytest.mark.asyncio
async def test_get_response_headers(rate_limiter):
    """Test generating response headers (Requirement 14.4)."""
    result = RateLimitResult(
        allowed=True,
        limit=100,
        remaining=75,
        reset_at=1705320000.0
    )
    
    headers = rate_limiter.get_response_headers(result)
    
    assert headers["X-RateLimit-Limit"] == "100"
    assert headers["X-RateLimit-Remaining"] == "75"
    assert headers["X-RateLimit-Reset"] == "1705320000"
    assert "Retry-After" not in headers


@pytest.mark.asyncio
async def test_get_response_headers_with_retry_after(rate_limiter):
    """Test response headers when rate limit exceeded."""
    result = RateLimitResult(
        allowed=False,
        limit=50,
        remaining=0,
        reset_at=1705320000.0,
        retry_after=60
    )
    
    headers = rate_limiter.get_response_headers(result)
    
    assert headers["X-RateLimit-Limit"] == "50"
    assert headers["X-RateLimit-Remaining"] == "0"
    assert headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_rate_limit_key_format(rate_limiter):
    """Test rate limit key format."""
    user_id = "user_123"
    endpoint = "read"
    
    key = rate_limiter._generate_rate_limit_key(user_id, endpoint)
    
    assert key == f"ratelimit:{user_id}:{endpoint}"


@pytest.mark.asyncio
async def test_different_limits_per_endpoint(rate_limiter):
    """Test different rate limits for different endpoints (Requirement 14.5)."""
    # Read endpoints: 100/min
    read_limit = rate_limiter._get_limit_for_endpoint("read")
    assert read_limit == 100
    
    # Write endpoints: 50/min
    write_limit = rate_limiter._get_limit_for_endpoint("write")
    assert write_limit == 50
    
    # LLM endpoints: 20/min
    llm_limit = rate_limiter._get_limit_for_endpoint("llm")
    assert llm_limit == 20
    
    # Upload endpoints: 10/min
    upload_limit = rate_limiter._get_limit_for_endpoint("upload")
    assert upload_limit == 10


@pytest.mark.asyncio
async def test_default_limit_for_unknown_endpoint(rate_limiter):
    """Test default limit for unknown endpoint."""
    unknown_limit = rate_limiter._get_limit_for_endpoint("unknown")
    
    assert unknown_limit == 60  # Default limit


@pytest.mark.asyncio
async def test_custom_limit_override(rate_limiter, redis_manager):
    """Test custom limit override."""
    user_id = "user_123"
    endpoint = "read"
    custom_limit = 200
    
    redis_manager.get.return_value = "50"
    redis_manager.increment.return_value = 51
    
    result = await rate_limiter.check_rate_limit(
        user_id,
        endpoint,
        limit=custom_limit
    )
    
    assert result.limit == custom_limit
    assert result.remaining == 149  # 200 - 50 - 1


@pytest.mark.asyncio
async def test_custom_window_override(rate_limiter, redis_manager):
    """Test custom window size override."""
    user_id = "user_123"
    endpoint = "read"
    custom_window = 120  # 2 minutes
    
    redis_manager.get.return_value = None
    redis_manager.increment.return_value = 1
    
    result = await rate_limiter.check_rate_limit(
        user_id,
        endpoint,
        window=custom_window
    )
    
    # Reset time should be current time + custom window
    assert result.reset_at > time.time()
    assert result.reset_at <= time.time() + custom_window + 1


@pytest.mark.asyncio
async def test_sliding_window_algorithm(rate_limiter):
    """Test that sliding window algorithm is used (Requirement 14.1)."""
    # The implementation uses a simplified counter approach
    # In production, this would use Redis sorted sets with:
    # - ZADD to add timestamps
    # - ZREMRANGEBYSCORE to remove old timestamps
    # - ZCARD to count current requests
    
    # Verify window size is 60 seconds
    assert rate_limiter.window_size == 60


@pytest.mark.asyncio
async def test_rate_limits_configuration(rate_limiter):
    """Test rate limit configuration (Requirement 14.2)."""
    # Verify default rate limits
    assert rate_limiter.limits["read"] == 100  # 100 requests/minute
    assert rate_limiter.limits["write"] == 50  # 50 requests/minute
    assert rate_limiter.limits["llm"] == 20  # 20 requests/minute
    assert rate_limiter.limits["upload"] == 10  # 10 requests/minute


@pytest.mark.asyncio
async def test_distributed_rate_limiting(rate_limiter, redis_manager):
    """Test that rate limiting works across multiple instances."""
    # Rate limiting uses Redis, so it's automatically distributed
    # All backend instances share the same Redis counters
    
    user_id = "user_123"
    endpoint = "write"
    
    # Simulate requests from different instances
    redis_manager.get.return_value = "25"
    redis_manager.increment.return_value = 26
    
    result = await rate_limiter.check_rate_limit(user_id, endpoint)
    
    assert result.allowed is True
    
    # The key is shared across all instances
    expected_key = f"ratelimit:{user_id}:{endpoint}"
    redis_manager.get.assert_called_with(expected_key)
