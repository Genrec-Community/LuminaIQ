from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # Main API Webhook
    MAIN_API_WEBHOOK_URL: str = "http://localhost:8000/api/v1/webhook/document-ready"
    MAIN_API_WEBHOOK_SECRET: str = "supersecretwebhook"

    # Application Configuration
    ENVIRONMENT: str = "development"

    # CORS - Allow frontend and main API
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # File Upload Configuration
    MAX_FILE_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "txt", "html", "md"]

    # Chunking Configuration (should match backend)
    CHUNK_SIZE: int = 800  # Larger chunks = fewer API calls
    CHUNK_OVERLAP: int = 100  # Better context continuity

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
