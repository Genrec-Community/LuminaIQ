from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from api.v1.api import api_router
from config.settings import settings
from utils.logger import setup_uvicorn_log_filter, logger
from middleware.rate_limit import RateLimitMiddleware
from middleware.telemetry import TelemetryMiddleware
import asyncio
import traceback

app = FastAPI(
    title="Lumina IQ API",
    description="Backend for Lumina IQ Education Platform",
    version="1.0.0",
)


# Global exception handler for telemetry tracking
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler to track all unhandled exceptions in telemetry.
    
    This handler ensures that all exceptions are tracked in Application Insights
    with full stack traces and context, even if they escape other error handling.
    
    Requirements:
    - 20.2: Send exception telemetry with stack traces to Application Insights
    
    Args:
        request: The request that caused the exception
        exc: The exception that was raised
        
    Returns:
        JSONResponse with error details
    """
    from core.telemetry import get_telemetry_service
    
    # Get correlation ID from request state if available
    correlation_id = getattr(request.state, "correlation_id", None)
    user_id = getattr(request.state, "user_id", None)
    project_id = getattr(request.state, "project_id", None)
    
    # Build context properties
    properties = {
        "method": request.method,
        "path": str(request.url.path),
        "query_params": str(request.query_params) if request.query_params else None,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "stack_trace": traceback.format_exc(),
    }
    
    if correlation_id:
        properties["correlation_id"] = correlation_id
    if user_id:
        properties["user_id"] = user_id
    if project_id:
        properties["project_id"] = project_id
    
    # Track exception in telemetry
    try:
        telemetry_service = get_telemetry_service()
        telemetry_service.track_exception(
            exception=exc,
            properties=properties
        )
    except Exception as telemetry_error:
        logger.error(f"Failed to track exception in telemetry: {telemetry_error}")
    
    # Log the exception
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {str(exc)}",
        exc_info=exc,
        extra={"properties": properties}
    )
    
    # Return error response
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
            "correlation_id": correlation_id,
        },
    )


# CORS Configuration
# Security Fix: Use explicit origins from settings
origins = settings.BACKEND_CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telemetry middleware (should be early in the chain to track all requests)
app.add_middleware(TelemetryMiddleware)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    # Apply log filter to reduce noisy HTTP logs
    setup_uvicorn_log_filter()
    
    # Initialize telemetry service
    try:
        from core.telemetry import initialize_telemetry
        telemetry_service = initialize_telemetry(
            service_name="lumina-backend",
            service_version="1.0.0"
        )
        if telemetry_service.enabled:
            logger.info("Azure Application Insights telemetry initialized successfully")
        else:
            logger.warning("Telemetry not configured - set APPLICATIONINSIGHTS_CONNECTION_STRING to enable")
    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {e}")
        logger.warning("Application will continue without telemetry")
    
    # Initialize Redis cache manager
    try:
        from core.redis_manager import initialize_redis_manager, get_redis_manager
        redis_manager = initialize_redis_manager()
        await redis_manager.connect()
        logger.info("Redis cache manager initialized successfully")
        
        # Inject Redis manager into embedding service
        try:
            from services.embedding_service import embedding_service
            embedding_service.redis_manager = get_redis_manager()
            logger.info("Redis manager injected into embedding service")
        except Exception as e:
            logger.warning(f"Failed to inject Redis manager into embedding service: {e}")
        
        # Warm cache with top 10 active projects
        try:
            from core.vector_cache import VectorSearchCache
            vector_cache = VectorSearchCache(redis_manager)
            warming_result = await vector_cache.warm_cache()
            
            if warming_result.get("success"):
                logger.info(
                    f"Cache warming completed successfully: "
                    f"{warming_result.get('projects_warmed', 0)} projects, "
                    f"{warming_result.get('documents_cached', 0)} documents, "
                    f"{warming_result.get('topics_cached', 0)} topics, "
                    f"{warming_result.get('knowledge_graphs_cached', 0)} knowledge graphs "
                    f"in {warming_result.get('duration_seconds', 0)}s"
                )
            else:
                logger.warning(
                    f"Cache warming failed: {warming_result.get('error', 'unknown error')}"
                )
        except Exception as e:
            logger.warning(f"Cache warming failed: {e}")
            logger.info("Application will continue without cache warming")
            
    except Exception as e:
        logger.error(f"Failed to initialize Redis cache manager: {e}")
        logger.warning("Application will continue without Redis caching")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    # Flush telemetry before shutdown
    try:
        from core.telemetry import get_telemetry_service
        telemetry_service = get_telemetry_service()
        telemetry_service.flush()
        logger.info("Telemetry flushed successfully")
    except Exception as e:
        logger.error(f"Error flushing telemetry: {e}")
    
    # Shutdown Redis manager
    try:
        from core.redis_manager import shutdown_redis_manager
        await shutdown_redis_manager()
        logger.info("Redis manager shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down Redis manager: {e}")
    
    # Shutdown embedding service
    try:
        from services.embedding_service import embedding_service
        embedding_service.shutdown()
    except Exception:
        pass
    
    # Stop embedding queue
    try:
        from utils.embedding_queue import get_embedding_queue
        queue = get_embedding_queue()
        await queue.stop()
    except Exception:
        pass


# Request timeout middleware — prevents a single stuck request from blocking others
class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip timeout for SSE streams and file uploads
        path = request.url.path
        if "/progress/" in path or "/upload" in path:
            return await call_next(request)
        try:
            return await asyncio.wait_for(call_next(request), timeout=90.0)
        except asyncio.TimeoutError:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=504,
                content={"detail": "Request timed out. Please try again."},
            )


app.add_middleware(RequestTimeoutMiddleware)


@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    logger.debug(f"INCOMING → {request.method} {request.url}")
    return await call_next(request)


# Handle CORS preflight requests to prevent hanging
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return Response(status_code=200)


app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Welcome to Lumina IQ API"}


@app.get("/health")
async def health():
    """
    Simple health check endpoint for liveness probes.
    
    Returns 200 OK if the service is running.
    Response time: < 100ms
    No dependency checks performed.
    
    Returns:
        dict: Health status with service name, version, and timestamp
    """
    from core.health_check import HealthCheckService
    from core.redis_manager import get_redis_manager
    from db.client import get_supabase_client
    from services.qdrant_service import qdrant_service
    
    try:
        # Create health check service
        health_service = HealthCheckService(
            redis_manager=get_redis_manager(),
            supabase_client=get_supabase_client(),
            qdrant_client=qdrant_service.async_client,
        )
        
        # Perform simple health check
        result = await health_service.check_health()
        return result.to_dict()
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        # Return healthy status even if health service fails
        # This is a liveness check, not a readiness check
        from datetime import datetime
        return {
            "status": "healthy",
            "service": "lumina-backend",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


@app.get("/health/ready")
async def health_ready():
    """
    Comprehensive readiness check endpoint for load balancer probes.
    
    Checks all critical dependencies:
    - Redis cache
    - Supabase database
    - Qdrant vector database
    - Azure OpenAI API
    
    Returns:
        dict: Readiness status with detailed dependency health information
        
    Status Codes:
        200 OK: All dependencies healthy (ready to serve traffic)
        503 Service Unavailable: One or more dependencies unhealthy
        
    Response time: < 1 second
    """
    from fastapi.responses import JSONResponse
    from core.health_check import HealthCheckService
    from core.redis_manager import get_redis_manager
    from db.client import get_supabase_client
    from services.qdrant_service import qdrant_service
    
    try:
        # Create health check service
        health_service = HealthCheckService(
            redis_manager=get_redis_manager(),
            supabase_client=get_supabase_client(),
            qdrant_client=qdrant_service.async_client,
        )
        
        # Perform comprehensive readiness check
        result = await health_service.check_readiness()
        
        # Return 503 if not ready, 200 if ready
        status_code = 200 if result.status.value == "ready" else 503
        
        return JSONResponse(
            status_code=status_code,
            content=result.to_dict(),
        )
    
    except Exception as e:
        logger.error(f"Readiness check failed with exception: {e}")
        # Return 503 if readiness check fails
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "error": f"Readiness check failed: {str(e)}",
            },
        )
