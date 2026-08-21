import os
import sys
import time
from contextlib import asynccontextmanager

# Ensure the app root is in PYTHONPATH
app_root = os.path.dirname(os.path.abspath(__file__))
if app_root not in sys.path:
    sys.path.insert(0, app_root)

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from api.v1.api import api_router
from build_info import BUILD_SHA
from config.settings import settings
from utils.logger import logger, setup_uvicorn_log_filter


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_uvicorn_log_filter()
    yield
    try:
        from services.embedding_service import embedding_service

        embedding_service.shutdown()
    except Exception:
        logger.exception("Failed to shut down embedding resources")
    try:
        from utils.embedding_queue import get_embedding_queue

        await get_embedding_queue().stop()
    except Exception:
        logger.exception("Failed to stop embedding queue")

app = FastAPI(
    title="Lumina IQ API",
    description="Backend for Lumina IQ Education Platform",
    version="1.0.0",
    lifespan=lifespan,
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


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 500

        async def send_with_status(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s %.1fms",
                scope.get("method", ""),
                scope.get("path", ""),
                status_code,
                duration_ms,
            )


app.add_middleware(RequestLoggingMiddleware)


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
    return {
        "status": "healthy",
        "service": "lumina-backend",
        "build_sha": BUILD_SHA,
    }
