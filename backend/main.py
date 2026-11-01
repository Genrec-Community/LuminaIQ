import os
import sys

# Ensure the app root is in PYTHONPATH
app_root = os.path.dirname(os.path.abspath(__file__))
if app_root not in sys.path:
    sys.path.insert(0, app_root)

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from api.v1.api import api_router
from config.settings import settings
from utils.logger import setup_uvicorn_log_filter
from utils.request_id import RequestIdMiddleware
import asyncio

app = FastAPI(
    title="Lumina IQ API",
    description="Backend for Lumina IQ Education Platform",
    version="1.0.0",
)

# CORS Configuration
# Security Fix: Use explicit origins from settings
origins = list(settings.BACKEND_CORS_ORIGINS)
# The Android app (Capacitor) serves the web build from these origins
for app_origin in ("https://localhost", "capacitor://localhost"):
    if app_origin not in origins:
        origins.append(app_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # The website on Azure Static Web Apps (its default *.azurestaticapps.net address)
    allow_origin_regex=r"https://[a-z0-9-]+(\.[a-z0-9]+)?\.azurestaticapps\.net",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Thread-Id"],   # the chat a streamed answer was saved to
)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    settings.validate_production()
    if settings.RUN_MIGRATIONS and settings.DATABASE_URL:
        # Bring the database schema up to date (safe when several instances start at once)
        from db.migrate import migrate
        from utils.logger import logger
        applied = await asyncio.to_thread(migrate)
        logger.info("Database schema " + (f"updated: {', '.join(applied)}" if applied else "up to date"))
    if settings.WORKER_INLINE and settings.DATABASE_URL:
        # Run queued background jobs in this process too (see utils/worker.py)
        from db.client import get_supabase_client
        from utils.worker import Worker
        import services.jobs  # noqa: F401  (registers the handlers)
        app.state.worker = Worker(get_supabase_client().pg, concurrency=settings.WORKER_CONCURRENCY,
                                  poll_seconds=settings.JOB_POLL_SECONDS,
                                  stale_seconds=settings.JOB_STALE_SECONDS)
        app.state.worker_task = asyncio.create_task(app.state.worker.run_forever())
    # Apply log filter to reduce noisy HTTP logs
    setup_uvicorn_log_filter()
    if settings.INDRA_OCR_URL:
        from utils.indra_ocr_client import keep_warm
        app.state.ocr_keep_warm = asyncio.create_task(keep_warm())
    if settings.SELF_CHECK_ON_STARTUP:
        from services.self_check import run_self_check
        app.state.self_check = asyncio.create_task(run_self_check())
    # Label schools whose paid term has ended (access already stops by date on its own)
    if settings.SCHOOL_EXPIRY_SWEEP:
        from services.institution_service import expiry_loop
        app.state.school_expiry = asyncio.create_task(expiry_loop())


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    worker = getattr(app.state, "worker", None)
    if worker:
        await worker.stop()   # let running jobs finish; queued ones wait for the next process
    try:
        from services.telemetry import telemetry
        await telemetry.flush()   # AI-call rows still in memory
    except Exception:
        pass
    try:
        from services.embedding_service import embedding_service
        embedding_service.shutdown()
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
# Outermost, so the id is set before anything else logs
app.add_middleware(RequestIdMiddleware)



# Handle CORS preflight requests to prevent hanging
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    return Response(status_code=200)


app.include_router(api_router, prefix="/api/v1")


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"message": "Welcome to Lumina IQ API"}


@app.get("/ready")
async def ready():
    """Readiness: 200 when Supabase (and the app Postgres / Redis, if configured) answer, else 503."""
    from fastapi.responses import JSONResponse
    from utils import readiness

    ok, checks = await readiness.check()
    return JSONResponse(status_code=200 if ok else 503,
                        content={"status": "ready" if ok else "not ready", "checks": checks})


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "lumina-backend"}
