from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from api.v1.api import api_router
from config.settings import settings
from utils.logger import setup_uvicorn_log_filter, logger
from middleware.rate_limit import RateLimitMiddleware
import asyncio

app = FastAPI(
    title="Lumina IQ API",
    description="Backend for Lumina IQ Education Platform",
    version="1.0.0",
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

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    # Apply log filter to reduce noisy HTTP logs
    setup_uvicorn_log_filter()
    
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
    """Health check endpoint"""
    return {"status": "healthy", "service": "lumina-backend"}
