from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str

    # Together AI Configuration
    TOGETHER_API_KEY: str

    # Qdrant Configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # Application Configuration
    ENVIRONMENT: str = "development"
    SECRET_KEY: str  # Ensure this is set in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "txt"]

    # LLM Configuration
    LLM_MODEL: str = "OpenAI/gpt-oss-20B"
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large-instruct"
    EMBEDDING_DIMENSION: int = 1024
    CHUNK_SIZE: int = 800  # Larger chunks = fewer API calls
    CHUNK_OVERLAP: int = 100  # Better context continuity

    # Rate Limiting for Together AI (600 req/min = 10 req/sec)
    EMBEDDING_BATCH_SIZE: int = 50  # Chunks per API call
    EMBEDDING_CONCURRENCY: int = 5  # Max parallel requests
    EMBEDDING_DELAY_MS: int = 200  # Delay between batches (ms)

    # Webhook Configuration (for PDF service communication)
    WEBHOOK_SECRET: str = "supersecretwebhook"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
