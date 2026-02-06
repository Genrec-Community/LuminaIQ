"""
Rate Limiter - DISABLED (No rate limiting)

Rate limiting has been removed as the API limits have been increased.
This module now provides pass-through methods with no delays.

Time Complexity: O(1) for acquire
Space Complexity: O(1)
"""

import asyncio
import time
from typing import Optional


class TokenBucketRateLimiter:
    """
    Token Bucket Rate Limiter - DISABLED.

    All requests pass through immediately with no delays.
    """

    def __init__(
        self,
        tokens_per_second: float = 1000.0,  # Effectively unlimited
        max_tokens: int = 1000,  # Effectively unlimited
        name: str = "default",
    ):
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.name = name

        # Stats only
        self._total_requests = 0
        self._total_waits = 0

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens - NO WAITING (rate limiting disabled).

        Returns: 0.0 (no wait time)
        """
        self._total_requests += 1
        return 0.0

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            "name": self.name,
            "total_requests": self._total_requests,
            "total_waits": self._total_waits,
            "current_tokens": self.max_tokens,
            "wait_ratio": 0.0,
            "status": "disabled - no rate limiting",
        }


class SlidingWindowRateLimiter:
    """
    Sliding Window Rate Limiter - DISABLED.

    All requests pass through immediately with no delays.
    """

    def __init__(self, requests_per_minute: int = 600, window_seconds: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds

    async def acquire(self) -> float:
        """Acquire permission to make a request - NO WAITING"""
        return 0.0


# Global rate limiters (singleton pattern)
_embedding_limiter: Optional[TokenBucketRateLimiter] = None
_llm_limiter: Optional[TokenBucketRateLimiter] = None


def get_embedding_limiter() -> TokenBucketRateLimiter:
    """Get the global embedding rate limiter (disabled - no rate limiting)"""
    global _embedding_limiter
    if _embedding_limiter is None:
        # No rate limiting - effectively unlimited
        _embedding_limiter = TokenBucketRateLimiter(
            tokens_per_second=1000.0, max_tokens=1000, name="embedding"
        )
    return _embedding_limiter


def get_llm_limiter() -> TokenBucketRateLimiter:
    """Get the global LLM rate limiter (disabled - no rate limiting)"""
    global _llm_limiter
    if _llm_limiter is None:
        # No rate limiting - effectively unlimited
        _llm_limiter = TokenBucketRateLimiter(
            tokens_per_second=1000.0, max_tokens=1000, name="llm"
        )
    return _llm_limiter
