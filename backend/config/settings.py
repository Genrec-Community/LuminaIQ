from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional, List
from typing_extensions import Annotated


class Settings(BaseSettings):
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str

    # Azure OpenAI Configuration (LLM)
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT: str
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    
    #Azure-Env

    MAIN_API_WEBHOOK_SECRET: str
    MAIN_API_WEBHOOK_URL: str

    # OpenAI-compatible API Configuration (Embeddings)
    EMBEDDING_API_KEY: str
    EMBEDDING_BASE_URL: str
    EMBEDDING_MODEL: str
    EMBEDDING_DIMENSION: int = 1024

    # Qdrant Configuration
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # Azure Application Insights Configuration
    APPLICATIONINSIGHTS_CONNECTION_STRING: Optional[str] = Field(default=None)
    APPINSIGHTS_INSTRUMENTATION_KEY: Optional[str] = Field(default=None)

    # Redis Configuration
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(ge=1, le=65535, default=6379)
    REDIS_PASSWORD: str = Field(default="")
    REDIS_DB: int = Field(ge=0, le=15, default=0)
    REDIS_SSL: bool = Field(default=False)
    REDIS_MAX_CONNECTIONS: int = Field(ge=10, le=100, default=50)
    REDIS_SOCKET_TIMEOUT: int = Field(ge=1, le=60, default=5)
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(ge=1, le=60, default=5)
    REDIS_RETRY_ATTEMPTS: int = Field(ge=0, le=10, default=3)

    # Cache TTL Configuration (in seconds)
    CACHE_TTL_EMBEDDING: int = Field(ge=3600, default=2592000)  # 30 days
    CACHE_TTL_QUERY: int = Field(ge=3600, default=604800)  # 7 days
    CACHE_TTL_VECTOR_SEARCH: int = Field(ge=60, default=3600)  # 1 hour
    CACHE_TTL_DOCUMENT: int = Field(ge=60, default=21600)  # 6 hours
    CACHE_TTL_SESSION: int = Field(ge=60, default=86400)  # 24 hours

    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2")
    CELERY_WORKER_CONCURRENCY: int = Field(ge=1, le=10, default=3)
    CELERY_TASK_TIME_LIMIT: int = Field(ge=60, default=600)  # 10 minutes
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(ge=60, default=540)  # 9 minutes
    CELERY_MAX_RETRIES: int = Field(ge=0, le=10, default=3)
    CELERY_RETRY_BACKOFF: int = Field(ge=1, default=2)  # Exponential backoff base

    # Together AI (optional - for some services)
    TOGETHER_API_KEY: str = Field(default="")

    # Application Configuration
    ENVIRONMENT: str = "development"
    SECRET_KEY: str  # Ensure this is set in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # ================================
    # 🌐 CORS (CRITICAL FIX)
    # ================================
    # BACKEND_CORS_ORIGINS=["https://www.luminaiq.fun","https://luminaiq.fun","http://localhost:5173"]
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "txt", "html", "md"]

    CHUNK_SIZE: int = 800  # Larger chunks = fewer API calls
    CHUNK_OVERLAP: int = 100  # Better context continuity

    # Rate Limiting for LLM API (adjust based on your plan limits)
    EMBEDDING_BATCH_SIZE: int = 50  # Chunks per API call
    EMBEDDING_CONCURRENCY: int = 5  # Max parallel requests
    EMBEDDING_DELAY_MS: int = 200  # Delay between batches (ms)

    # Webhook Configuration (for PDF service communication)
    WEBHOOK_SECRET: str = "supersecretwebhook"

    # Pydantic validators for configuration validation
    @field_validator("REDIS_HOST")
    @classmethod
    def validate_redis_host(cls, v: str) -> str:
        """Validate that REDIS_HOST is not empty."""
        if not v or v.strip() == "":
            raise ValueError("REDIS_HOST must be set and cannot be empty")
        return v.strip()

    @field_validator("REDIS_PORT")
    @classmethod
    def validate_redis_port(cls, v: int) -> int:
        """Validate that REDIS_PORT is in valid range."""
        if not (1 <= v <= 65535):
            raise ValueError(f"REDIS_PORT must be between 1 and 65535, got {v}")
        return v

    @field_validator("REDIS_DB")
    @classmethod
    def validate_redis_db(cls, v: int) -> int:
        """Validate that REDIS_DB is in valid range (0-15 for standard Redis)."""
        if not (0 <= v <= 15):
            raise ValueError(f"REDIS_DB must be between 0 and 15, got {v}")
        return v

    @field_validator("CACHE_TTL_EMBEDDING", "CACHE_TTL_QUERY")
    @classmethod
    def validate_long_ttl(cls, v: int) -> int:
        """Validate that long-term cache TTLs are at least 1 hour."""
        if v < 3600:
            raise ValueError(f"Long-term cache TTL must be at least 3600 seconds (1 hour), got {v}")
        return v

    @field_validator("CACHE_TTL_VECTOR_SEARCH", "CACHE_TTL_DOCUMENT", "CACHE_TTL_SESSION")
    @classmethod
    def validate_short_ttl(cls, v: int) -> int:
        """Validate that short-term cache TTLs are at least 1 minute."""
        if v < 60:
            raise ValueError(f"Short-term cache TTL must be at least 60 seconds (1 minute), got {v}")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
