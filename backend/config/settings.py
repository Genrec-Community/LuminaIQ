from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, DotEnvSettingsSource, EnvSettingsSource
from pydantic import Field, field_validator
from typing import Any, ClassVar, Dict, List, Optional, Union


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
    # Chat models: any OpenAI-compatible API (OpenAI, Azure /openai/v1, Groq,
    # Together, OpenRouter, vLLM, Ollama ...). See services/llm_service.py.
    # ─────────────────────────────────────────────────────────
    # Most work, and every request from free users
    SMALL_LLM_MODEL: str = Field(default="")
    SMALL_LLM_BASE_URL: str = Field(default="")
    SMALL_LLM_API_KEY: str = Field(default="")
    SMALL_LLM_REASONING_EFFORT: str = Field(default="")   # e.g. low | medium | high, if supported
    # Deep answers, Visual Lab builds, photo questions (paid plans). Empty = small model.
    # Base URL and key default to the small model's.
    BIG_LLM_MODEL: str = Field(default="")
    BIG_LLM_BASE_URL: str = Field(default="")
    BIG_LLM_API_KEY: str = Field(default="")
    BIG_LLM_REASONING_EFFORT: str = Field(default="")
    LLM_TIMEOUT_SECONDS: float = 120.0
    # Older names, still read when the SMALL_LLM_* ones are empty
    LLM_API_KEY: str = Field(default="")
    LLM_BASE_URL: str = Field(default="")
    LLM_MODEL: str = Field(default="")
    LLM_REASONING_EFFORT: str = Field(default="")

    # Optional reranker (Cohere/Jina-style /rerank). On only when the key is set.
    RERANK_API_KEY: str = Field(default="")
    RERANK_BASE_URL: str = Field(default="https://api.cohere.com/v2")
    RERANK_MODEL: str = Field(default="rerank-v3.5")

    # ── Razorpay (payments) ── fill these in Render; empty = payments disabled
    RAZORPAY_KEY_ID: str = Field(default="")            # rzp_test_... / rzp_live_...
    RAZORPAY_KEY_SECRET: str = Field(default="")
    RAZORPAY_WEBHOOK_SECRET: str = Field(default="")    # set when creating the webhook
    # Optional Razorpay Subscription plan IDs. When set, Scholar / Topper renew
    # automatically. When empty, students pay once for a month or a year (one-time
    # order, no auto-renewal), which needs no setup beyond the keys.
    # scripts/create_razorpay_plans.py creates the plans and prints the IDs.
    RAZORPAY_PLAN_SCHOLAR_MONTHLY: str = Field(default="")
    RAZORPAY_PLAN_SCHOLAR_YEARLY: str = Field(default="")
    RAZORPAY_PLAN_TOPPER_MONTHLY: str = Field(default="")
    RAZORPAY_PLAN_TOPPER_YEARLY: str = Field(default="")
    # ── Schools (institution plan) ──
    # Domain of school-created student sign-in IDs (studentname-07@luminaiq.fun).
    # These are sign-in names only: no mailbox exists and no email is ever sent to them.
    STUDENT_LOGIN_DOMAIN: str = Field(default="luminaiq.fun")
    # New schools wait for a platform admin to approve them before anything works.
    INSTITUTION_REQUIRE_APPROVAL: bool = Field(default=True)
    # Free trial given when a school is approved (0 = no trial: pay first).
    INSTITUTION_TRIAL_DAYS: int = Field(default=14)
    # Our GSTIN. Empty = no GST is added to school prices; set it to add 18% GST.
    INSTITUTION_GSTIN: str = Field(default="")
    # Comma-separated emails that can use the platform admin console (/platform),
    # in addition to users with the 'owner' or 'admin' role in user_roles.
    PLATFORM_ADMIN_EMAILS: str = Field(default="")
    # Day boundary for daily plan limits
    PLAN_TIMEZONE: str = Field(default="Asia/Kolkata")
    # Enforce the per-plan limits in services/plans.py. With false, usage is still
    # counted but nothing is blocked (every plan is effectively unlimited).
    PLAN_LIMITS_ENABLED: bool = Field(default=True)
    # On boot, make one tiny call to the LLM, embeddings, Qdrant and storage and log
    # "[SelfCheck] ..." lines (see services/self_check.py)
    SELF_CHECK_ON_STARTUP: bool = Field(default=True)
    # Hourly sweep that marks schools whose paid term ended as expired.
    # Off on the test backend, which shares the live database.
    SCHOOL_EXPIRY_SWEEP: bool = Field(default=True)

    # Webhook
    MAIN_API_WEBHOOK_SECRET: str = Field(default="supersecretwebhook")
    MAIN_API_WEBHOOK_URL: str = Field(default="http://localhost:8000/api/v1/webhook/document-ready")

    # ─────────────────────────────────────────────────────────
    # Embeddings: any OpenAI-compatible /embeddings API
    # ─────────────────────────────────────────────────────────
    EMBEDDING_API_KEY: str = Field(default="")    # empty = the small chat model's key
    EMBEDDING_BASE_URL: str = Field(default="")   # empty = the small chat model's base URL
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    # Must match the model. Fixed when the chunks table is created (db/schema/0004).
    EMBEDDING_DIMENSION: int = 1536
    # Send "dimensions" (models that can shorten vectors, e.g. text-embedding-3-*, Gemini)
    EMBEDDING_SEND_DIMENSIONS: bool = Field(default=False)

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
    MAX_GLOBAL_DB_OPERATIONS: int = 10      # concurrent vector writes
    MAX_GLOBAL_EMBEDDINGS: int = 5         # Concurrent embedding API calls
    MAX_CONCURRENT_LLM: int = 3             # Concurrent LLM calls (topic/graph gen)

    # Batch size for embedding API calls
    EMBEDDING_BATCH_SIZE: int = 50
    EMBEDDING_DELAY_MS: int = 0  # 0 = no artificial delay (Azure has no rate limits)

    # Gunicorn workers for production
    # Recommended: (2 * CPU cores) + 1. Azure 1-core = 3 workers.
    GUNICORN_WORKERS: int = 3
    GUNICORN_MAX_REQUESTS: int = 20000   # requests before a worker is recycled

    # Webhook secret
    WEBHOOK_SECRET: str = "supersecretwebhook"

    # ─────────────────────────────────────────────────────────
    # Book Store
    # ─────────────────────────────────────────────────────────
    BOOK_STORE_PAGE_SIZE: int = 20
    BOOK_STORE_MAX_DESCRIPTION: int = 2000
    BOOK_IMPORT_TEXTS_BUCKET: str = "texts"   # Supabase bucket for extracted .txt files

    # ─────────────────────────────────────────────────────────
    # App database (all tables, pgvector, job queue, caches) and optional Redis
    # ─────────────────────────────────────────────────────────
    # Docker Postgres in development, AWS RDS in production. Empty = not configured yet.
    DATABASE_URL: str = Field(default="")
    DB_POOL_SIZE: int = 10          # connections per process
    DB_THREADS: int = 32            # threads running database/storage calls per process
    RUN_MIGRATIONS: bool = True     # apply db/schema on startup

    # Background jobs. WORKER_INLINE runs a worker inside each web process (dev, single box);
    # set it to false when separate `uv run worker.py` processes do the work.
    WORKER_INLINE: bool = True
    WORKER_CONCURRENCY: int = 2       # jobs at once per worker (book processing is heavy)
    JOB_POLL_SECONDS: float = 1.0
    JOB_STALE_SECONDS: float = 300.0  # a running job with no heartbeat for this long is retried

    # Per-user rate limits (floods and runaway clients; plan quotas are separate)
    RATE_LIMITS_ENABLED: bool = True
    RATE_LIMIT_CHAT_PER_MIN: int = 20
    RATE_LIMIT_GENERATE_PER_MIN: int = 10
    RATE_LIMIT_UPLOAD_PER_HOUR: int = 30

    # Optional moderation API (OpenAI-compatible /moderations) for school-level chat
    MODERATION_BASE_URL: str = Field(default="")
    MODERATION_API_KEY: str = Field(default="")
    MODERATION_MODEL: str = Field(default="omni-moderation-latest")
    # Optional: hot cache, rate limits and progress pub/sub. Empty = off.
    REDIS_URL: str = Field(default="")

    # Placeholder values that must never reach production
    DEFAULT_SECRETS: ClassVar[Dict[str, str]] = {
        "SECRET_KEY": "supersecretkey",
        "WEBHOOK_SECRET": "supersecretwebhook",
        "MAIN_API_WEBHOOK_SECRET": "supersecretwebhook",
    }

    def validate_production(self) -> None:
        """Refuse to start in production while any secret still has its placeholder value."""
        if self.ENVIRONMENT != "production":
            return
        weak = [name for name, default in self.DEFAULT_SECRETS.items()
                if not getattr(self, name) or getattr(self, name) == default]
        if weak:
            raise RuntimeError(
                "Refusing to start in production with default secrets: " + ", ".join(weak)
                + ". Set them in the environment."
            )

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
        # backend/.env wins over the repo-root .env (which docker compose also reads)
        env_file = ("../.env", ".env")
        case_sensitive = True
        extra = "ignore"


settings = Settings()
