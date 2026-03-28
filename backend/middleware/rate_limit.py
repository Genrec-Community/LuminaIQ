"""Rate limiting middleware for FastAPI.

**Validates: Requirements 14.3, 14.4**

This middleware enforces rate limits on API requests using the Redis-based
RateLimiter. It checks rate limits before processing requests and adds
appropriate headers to responses.
"""

import logging
from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.rate_limiter import RateLimiter, RateLimitResult
from core.redis_manager import get_redis_manager

logger = logging.getLogger(__name__)


# Endpoint category mapping
ENDPOINT_CATEGORIES = {
    # Read endpoints
    "/api/v1/documents": "read",
    "/api/v1/mcq/topics": "read",
    "/api/v1/knowledge_graph": "read",
    "/api/v1/progress": "read",
    "/api/v1/jobs": "read",
    "/api/v1/cache/stats": "read",
    "/health": "read",
    
    # Write endpoints
    "/api/v1/documents/upload": "write",
    "/api/v1/notes": "write",
    "/api/v1/flashcards": "write",
    "/api/v1/projects": "write",
    
    # LLM endpoints
    "/api/v1/chat": "llm",
    "/api/v1/mcq/generate": "llm",
    "/api/v1/knowledge_graph/build": "llm",
    
    # Upload endpoints
    "/api/v1/documents/upload": "upload",
}


def get_endpoint_category(path: str) -> str:
    """
    Determine the rate limit category for an endpoint.
    
    Args:
        path: Request path
        
    Returns:
        Endpoint category (read, write, llm, upload, default)
    """
    # Check for exact matches first
    if path in ENDPOINT_CATEGORIES:
        return ENDPOINT_CATEGORIES[path]
    
    # Check for prefix matches
    for endpoint_prefix, category in ENDPOINT_CATEGORIES.items():
        if path.startswith(endpoint_prefix):
            return category
    
    # Default category
    return "default"


def get_user_id_from_request(request: Request) -> Optional[str]:
    """
    Extract user ID from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User ID if authenticated, None otherwise
    """
    # Try to get user_id from request state (set by auth middleware)
    if hasattr(request.state, "user_id"):
        return request.state.user_id
    
    # Try to get from headers (for testing)
    user_id = request.headers.get("X-User-ID")
    if user_id:
        return user_id
    
    # Fallback to IP address for unauthenticated requests
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    
    Checks rate limits before processing requests and adds rate limit headers
    to responses. Returns 429 Too Many Requests when limits are exceeded.
    
    Requirements:
    - 14.3: Return 429 with Retry-After header when limit exceeded
    - 14.4: Add rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
    """
    
    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application
            rate_limiter: RateLimiter instance (optional, will create if not provided)
        """
        super().__init__(app)
        
        # Initialize rate limiter
        if rate_limiter is None:
            redis_manager = get_redis_manager()
            if redis_manager:
                self.rate_limiter = RateLimiter(redis_manager)
                logger.info("[RateLimitMiddleware] Initialized with Redis-based rate limiter")
            else:
                self.rate_limiter = None
                logger.warning(
                    "[RateLimitMiddleware] Redis unavailable, rate limiting disabled"
                )
        else:
            self.rate_limiter = rate_limiter
            logger.info("[RateLimitMiddleware] Initialized with provided rate limiter")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with rate limiting.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response with rate limit headers
        """
        # Skip rate limiting if rate limiter not available
        if self.rate_limiter is None:
            logger.debug(
                "[RateLimitMiddleware] Rate limiter unavailable, skipping rate limit check"
            )
            return await call_next(request)
        
        # Skip rate limiting for health check endpoints
        if request.url.path in ["/health", "/health/ready"]:
            return await call_next(request)
        
        # Get user ID and endpoint category
        user_id = get_user_id_from_request(request)
        endpoint_category = get_endpoint_category(request.url.path)
        
        # Check rate limit
        try:
            result: RateLimitResult = await self.rate_limiter.check_rate_limit(
                user_id=user_id,
                endpoint=endpoint_category
            )
            
            # Generate rate limit headers
            headers = self.rate_limiter.get_response_headers(result)
            
            # If rate limit exceeded, return 429
            if not result.allowed:
                logger.warning(
                    f"[RateLimitMiddleware] Rate limit exceeded for user={user_id}, "
                    f"endpoint={endpoint_category}, path={request.url.path}"
                )
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Please try again later.",
                        "limit": result.limit,
                        "remaining": result.remaining,
                        "reset_at": int(result.reset_at)
                    },
                    headers=headers
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to response
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value
            
            logger.debug(
                f"[RateLimitMiddleware] Request allowed for user={user_id}, "
                f"endpoint={endpoint_category}, remaining={result.remaining}"
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"[RateLimitMiddleware] Error checking rate limit: {e}",
                exc_info=True
            )
            # On error, allow request to proceed (fail open)
            return await call_next(request)
