from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, DotEnvSettingsSource, EnvSettingsSource
from pydantic import Field, field_validator
from typing import Optional, List, Union, Any


class CustomDotEnvSettingsSource(DotEnvSettingsSource):
    def decode_complex_value(self, field_name: str, field: Any, value: Any) -> Any:
        if field_name == "BACKEND_CORS_ORIGINS" and isinstance(value, str):
            if not value.strip().startswith("["):
                return [origin.strip() for origin in value.split(",") if origin.strip()]
        try:
            return super().decode_complex_value(field_name, field, value)
        except Exception:
            if isinstance(value, str):
                return [origin.strip() for origin in value.split(",") if origin.strip()]
            raise


class CustomEnvSettingsSource(EnvSettingsSource):
    def decode_complex_value(self, field_name: str, field: Any, value: Any) -> Any:
        if field_name == "BACKEND_CORS_ORIGINS" and isinstance(value, str):
            if not value.strip().startswith("["):
                return [origin.strip() for origin in value.split(",") if origin.strip()]
        try:
            return super().decode_complex_value(field_name, field, value)
        except Exception:
            if isinstance(value, str):
                return [origin.strip() for origin in value.split(",") if origin.strip()]
            raise


class Settings(BaseSettings):
    # Supabase Configuration
    SUPABASE_URL: str = Field(default="")
    SUPABASE_KEY: str = Field(default="")
    SUPABASE_SERVICE_KEY: str = Field(default="")

    # ─────────────────────────────────────────────────────────
    # Unified / Single Variable for Model API Key
    # ─────────────────────────────────────────────────────────
    MODEL_API_KEY: Optional[str] = None

    # ─────────────────────────────────────────────────────────
    # Azure OpenAI (primary LLM — used for chat, topics, graph)
    # .env keys: AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
    #            AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
    # ─────────────────────────────────────────────────────────
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"

    # Deployment name in Azure (your .env uses AZURE_OPENAI_DEPLOYMENT)
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-5-mini"

    # Alias kept for backward-compat with any service that imports this name
    @property
    def AZURE_OPENAI_CHAT_DEPLOYMENT(self) -> str:
        return self.AZURE_OPENAI_DEPLOYMENT

    # Embedding deployment name (Azure OpenAI — text-embedding-3-small)
    AZURE_OPENAI_EMBED_DEPLOYMENT: str = "text-embedding-3-small"

    # ─────────────────────────────────────────────────────────
    # Legacy OpenAI-compatible LLM fields
    # Kept so any old service import doesn't crash.
    # Defaults to Azure values so they're usable even if not set.
    # ─────────────────────────────────────────────────────────
    LLM_API_KEY: str = Field(default="")
    LLM_BASE_URL: str = Field(default="")
    LLM_MODEL: str = Field(default="gpt-4.1-mini")
    # Which chat model provider to use:
    #   "auto"   → Azure OpenAI if configured, otherwise the OpenAI-compatible LLM_* provider
    #   "azure"  → always Azure OpenAI
    #   "openai" → always the OpenAI-compatible provider (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL),
    #              e.g. Inception Mercury, while embeddings can still use Azure
    LLM_PROVIDER: str = Field(default="auto")
    # Optional reasoning effort for providers that support it (e.g. Mercury: "low" | "medium" | "high")
    LLM_REASONING_EFFORT: str = Field(default="")
    # Optional cheaper model (same provider, base URL and key) for bulk structured
    # work: quiz questions, flashcards, mindmaps, topic summaries and knowledge-graph
    # links. Empty = everything uses LLM_MODEL. Not used with Azure.
    LLM_LIGHT_MODEL: str = Field(default="")
    # Optional stronger "Deep" model: Topper chat answers in Deep mode, Topper cram
    # cards and Visual Lab builds. Empty = LLM_MODEL. Base URL / key default to the
    # main provider's, so a different OpenAI-compatible provider can be used here.
    LLM_DEEP_MODEL: str = Field(default="")
    LLM_DEEP_BASE_URL: str = Field(default="")
    LLM_DEEP_API_KEY: str = Field(default="")
    # ── Razorpay (payments) ── fill these in Render; empty = payments disabled
    RAZORPAY_KEY_ID: str = Field(default="")            # rzp_test_... / rzp_live_...
    RAZORPAY_KEY_SECRET: str = Field(default="")
    RAZORPAY_WEBHOOK_SECRET: str = Field(default="")    # set when creating the webhook
    # Plan IDs from Razorpay (scripts/create_razorpay_plans.py creates them)
    RAZORPAY_PLAN_SCHOLAR_MONTHLY: str = Field(default="")
    RAZORPAY_PLAN_SCHOLAR_YEARLY: str = Field(default="")
    RAZORPAY_PLAN_TOPPER_MONTHLY: str = Field(default="")
    RAZORPAY_PLAN_TOPPER_YEARLY: str = Field(default="")
    # Day boundary for daily plan limits
    PLAN_TIMEZONE: str = Field(default="Asia/Kolkata")
    # On boot, make one tiny call to the LLM, embeddings, Qdrant and storage and log
    # "[SelfCheck] ..." lines (see services/self_check.py)
    SELF_CHECK_ON_STARTUP: bool = Field(default=True)

    # Webhook
    MAIN_API_WEBHOOK_SECRET: str = Field(default="supersecretwebhook")
    MAIN_API_WEBHOOK_URL: str = Field(default="http://localhost:8000/api/v1/webhook/document-ready")

    # ─────────────────────────────────────────────────────────
    # Embeddings — Azure OpenAI / OpenAI-compatible
    # ─────────────────────────────────────────────────────────
    EMBEDDING_API_KEY: str = Field(default="")
    EMBEDDING_BASE_URL: str = Field(default="")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    EMBEDDING_DIMENSION: int = 1536
    # "auto" → Azure if configured, else OpenAI-compatible EMBEDDING_BASE_URL/EMBEDDING_API_KEY;
    # "azure" or "openai" to force one. EMBEDDING_DIMENSION must match the chosen model.
    EMBEDDING_PROVIDER: str = Field(default="auto")
    # Ask the provider to return EMBEDDING_DIMENSION-sized vectors (the OpenAI
    # "dimensions" parameter). Use with models that support shortening, e.g.
    # Gemini gemini-embedding-001 (768/1536/3072) or OpenAI text-embedding-3-*.
    EMBEDDING_SEND_DIMENSIONS: bool = Field(default=False)

    # ─────────────────────────────────────────────────────────
    # Qdrant Vector Store
    # ─────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None

    # ─────────────────────────────────────────────────────────
    # Azure Computer Vision — OCR for scanned PDFs and images
    # ─────────────────────────────────────────────────────────
    # Set these to enable cloud OCR (replaces local Tesseract fallback).
    # Format: https://<region>.api.cognitive.microsoft.com/
    AZURE_CV_ENDPOINT: str = ""
    AZURE_CV_KEY: str = ""
    # Google Cloud Vision OCR for scanned PDFs: service-account JSON key, raw or base64
    GOOGLE_VISION_CREDENTIALS: str = ""
    # Self-hosted Indra OCR service (ocr-service/), tried before Google Vision
    INDRA_OCR_URL: str = ""
    INDRA_OCR_TOKEN: str = ""
    # Pages per calendar month (UTC) sent to Google Vision; the rest use Tesseract.
    # Google's free tier is 1,000 pages a month, so this stays under it.
    GOOGLE_VISION_MONTHLY_PAGES: int = 900
    # Local OCR (Tesseract, in the Docker image) for scanned PDFs when Azure isn't set
    OCR_LOCAL_ENABLED: bool = True
    OCR_DPI: int = 200
    OCR_MAX_PAGES: int = 600

    # Together AI (optional - for some services)
    TOGETHER_API_KEY: str = Field(default="")

    # ─────────────────────────────────────────────────────────
    # Application
    # ─────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    SECRET_KEY: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://lumina-iq-livid.vercel.app",
        "https://luminaiq.fun",
        "https://www.luminaiq.fun",
        "https://test.luminaiq.fun",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("["):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 104857600  # 100MB
    ALLOWED_EXTENSIONS: List[str] = [
        "pdf", "docx", "txt", "html", "md",
        # Image formats — processed via Azure CV OCR
        "jpg", "jpeg", "png", "bmp", "tiff", "tif", "gif", "webp",
    ]

    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 80

    # ─────────────────────────────────────────────────────────
    # Concurrency — all limits in one place for easy tuning
    # ─────────────────────────────────────────────────────────

    # General LLM-heavy operations (chat, quiz, notes, knowledge graph, etc.)
    MAX_CONCURRENT_GENERAL: int = 40

    # Document upload + embedding pipeline
    MAX_CONCURRENT_DOCUMENT_UPLOADS: int = 2

    # Global limits inside the embedding pipeline (shared across all docs)
    MAX_GLOBAL_DB_OPERATIONS: int = 10      # Qdrant write concurrency
    MAX_GLOBAL_EMBEDDINGS: int = 5         # Concurrent embedding API calls
    MAX_CONCURRENT_LLM: int = 3             # Concurrent LLM calls (topic/graph gen)

    # Batch size for embedding API calls
    EMBEDDING_BATCH_SIZE: int = 50
    EMBEDDING_DELAY_MS: int = 0  # 0 = no artificial delay (Azure has no rate limits)

    # Gunicorn workers for production
    # Recommended: (2 * CPU cores) + 1. Azure 1-core = 3 workers.
    GUNICORN_WORKERS: int = 3

    # Webhook secret
    WEBHOOK_SECRET: str = "supersecretwebhook"

    # ─────────────────────────────────────────────────────────
    # Book Store
    # ─────────────────────────────────────────────────────────
    BOOK_STORE_PAGE_SIZE: int = 20
    BOOK_STORE_MAX_DESCRIPTION: int = 2000
    BOOK_IMPORT_TEXTS_BUCKET: str = "texts"   # Supabase bucket for extracted .txt files

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            CustomEnvSettingsSource(settings_cls),
            CustomDotEnvSettingsSource(
                settings_cls,
                env_file=dotenv_settings.env_file,
                env_file_encoding=dotenv_settings.env_file_encoding,
                case_sensitive=dotenv_settings.case_sensitive,
                env_prefix=dotenv_settings.env_prefix,
            ),
            file_secret_settings,
        )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
