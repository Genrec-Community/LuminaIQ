from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.api import api_router
from config.settings import settings
from utils.logger import setup_uvicorn_log_filter

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
    # Apply log filter to reduce noisy HTTP logs
    setup_uvicorn_log_filter()


app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Welcome to Lumina IQ API"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "lumina-backend"}
