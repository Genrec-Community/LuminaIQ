from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from api.v1.api import api_router
from config.settings import settings
from utils.logger import setup_logging, logger
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


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Starting Lumina IQ API...")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    try:
        from services.embedding_service import embedding_service
        embedding_service.shutdown()
    except Exception:
        pass
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
    logger.info(f"INCOMING → {request.method} {request.url}")
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
