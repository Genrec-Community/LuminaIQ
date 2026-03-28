"""Request telemetry middleware for Azure Application Insights.

**Validates: Requirements 20.1, 20.5**

This middleware tracks all HTTP requests with comprehensive telemetry including:
- Request duration
- Status code
- Endpoint
- Correlation ID (for distributed tracing)
- User ID (for user-specific analytics)
- Project ID (for project-specific analytics)
- Cache status (HIT/MISS for cache performance tracking)
"""

import logging
import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.telemetry import get_telemetry_service

logger = logging.getLogger(__name__)


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
    
    return None


def get_project_id_from_request(request: Request) -> Optional[str]:
    """
    Extract project ID from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Project ID if present in request, None otherwise
    """
    # Try to get project_id from request state
    if hasattr(request.state, "project_id"):
        return request.state.project_id
    
    # Try to get from query parameters
    project_id = request.query_params.get("project_id")
    if project_id:
        return project_id
    
    # Try to get from path parameters
    if hasattr(request, "path_params"):
        project_id = request.path_params.get("project_id")
        if project_id:
            return project_id
    
    return None


def get_cache_status_from_response(response: Response) -> Optional[str]:
    """
    Extract cache status from response headers.
    
    Args:
        response: FastAPI response object
        
    Returns:
        Cache status (HIT/MISS) if present, None otherwise
    """
    # Check for X-Cache-Status header
    if hasattr(response, "headers"):
        return response.headers.get("X-Cache-Status")
    
    return None


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    Request telemetry middleware for Azure Application Insights.
    
    Tracks comprehensive request telemetry including:
    - Request duration (in milliseconds)
    - HTTP status code
    - Endpoint (method + path)
    - Correlation ID (unique per request for distributed tracing)
    - User ID (for user-specific analytics)
    - Project ID (for project-specific analytics)
    - Cache status (HIT/MISS for cache performance tracking)
    
    Requirements:
    - 20.1: Send request telemetry (duration, status code, endpoint) to Application Insights
    - 20.5: Include Correlation_ID in all telemetry for request tracing
    """
    
    def __init__(self, app):
        """
        Initialize telemetry middleware.
        
        Args:
            app: FastAPI application
        """
        super().__init__(app)
        self.telemetry_service = get_telemetry_service()
        
        if self.telemetry_service.enabled:
            logger.info("[TelemetryMiddleware] Initialized with Application Insights")
        else:
            logger.warning(
                "[TelemetryMiddleware] Application Insights not configured, "
                "telemetry tracking disabled"
            )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with telemetry tracking.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response with correlation ID header
        """
        # Generate unique correlation ID for this request
        correlation_id = str(uuid.uuid4())
        
        # Store correlation ID in request state for access by other components
        request.state.correlation_id = correlation_id
        
        # Record start time
        start_time = time.time()
        
        # Extract user ID and project ID
        user_id = get_user_id_from_request(request)
        project_id = get_project_id_from_request(request)
        
        # Store in request state for downstream use
        if user_id:
            request.state.user_id = user_id
        if project_id:
            request.state.project_id = project_id
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration in milliseconds
            duration_ms = (time.time() - start_time) * 1000
            
            # Extract cache status from response
            cache_status = get_cache_status_from_response(response)
            
            # Build custom properties
            properties = {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params) if request.query_params else None,
            }
            
            # Add user_id if present
            if user_id:
                properties["user_id"] = user_id
            
            # Add project_id if present
            if project_id:
                properties["project_id"] = project_id
            
            # Add cache_status if present
            if cache_status:
                properties["cache_status"] = cache_status
            
            # Track request telemetry
            endpoint_name = f"{request.method} {request.url.path}"
            self.telemetry_service.track_request(
                name=endpoint_name,
                duration=duration_ms,
                status_code=response.status_code,
                properties=properties
            )
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Log slow requests (> 500ms)
            if duration_ms > 500:
                logger.warning(
                    f"[TelemetryMiddleware] Slow request detected: "
                    f"{endpoint_name} took {duration_ms:.2f}ms "
                    f"(correlation_id={correlation_id})"
                )
            
            return response
            
        except Exception as e:
            # Calculate duration even for failed requests
            duration_ms = (time.time() - start_time) * 1000
            
            # Build custom properties for exception
            properties = {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "exception_type": type(e).__name__,
            }
            
            if user_id:
                properties["user_id"] = user_id
            if project_id:
                properties["project_id"] = project_id
            
            # Track exception telemetry
            self.telemetry_service.track_exception(
                exception=e,
                properties=properties
            )
            
            # Track failed request telemetry (status code 500)
            endpoint_name = f"{request.method} {request.url.path}"
            self.telemetry_service.track_request(
                name=endpoint_name,
                duration=duration_ms,
                status_code=500,
                properties=properties
            )
            
            logger.error(
                f"[TelemetryMiddleware] Request failed: {endpoint_name} "
                f"(correlation_id={correlation_id})",
                exc_info=e
            )
            
            # Re-raise exception to be handled by FastAPI exception handlers
            raise
