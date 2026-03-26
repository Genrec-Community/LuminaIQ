from pydantic_settings import BaseSettings
from pydantic import Field
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

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
