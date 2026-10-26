"""Application configuration powered by Pydantic Settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core Application Settings
    APP_NAME: str = "CareerAI"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Database Settings
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./careerai_dev.db",
        description="SQLAlchemy async connection string (mysql+asyncmy://... or sqlite+aiosqlite://...)",
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # Redis Cache & Background Tasks
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # Security & JWT Auth
    SECRET_KEY: str = "insecure-secret-key-change-in-production-min32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Storage Settings
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    STORAGE_LOCAL_ROOT: str = "./storage/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # AWS Settings (used when STORAGE_BACKEND=s3 or deployed to AWS)
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "careerai-documents-bucket"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # ML Configuration
    MODEL_DIR: str = "./app/ml/artifacts"
    DEFAULT_MODEL_VERSION: str = "v1.0.0"

    # LLM Settings
    LLM_PROVIDER: str = "ollama"  # "ollama" | "mock" | "openai" | "groq" | "gemini" | "openrouter"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3.2"
    LLM_TIMEOUT_SECONDS: int = 120
    LLM_MAX_RETRIES: int = 3

    # RAG & Vector Store Settings
    VECTOR_STORE_TYPE: str = "memory"  # "memory" | "chroma" | "qdrant"
    VECTOR_STORE_PATH: str = "./storage/vector_store"
    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 384

    # Rate Limiting
    RATE_LIMIT_AUTH_PER_MINUTE: int = 20
    RATE_LIMIT_AI_PER_MINUTE: int = 10

    @property
    def resolved_ollama_base_url(self) -> str:
        """Resolve base URL for local Ollama HTTP API."""
        url = self.OLLAMA_BASE_URL or "http://localhost:11434"
        return url.rstrip("/")

    @property
    def resolved_llm_base_url(self) -> str:
        """Resolve LLM base URL based on provider if not explicitly customized."""
        provider = self.LLM_PROVIDER.lower()
        if provider == "ollama":
            return self.resolved_ollama_base_url
        if self.LLM_BASE_URL and self.LLM_BASE_URL != "https://api.openai.com/v1":
            return self.LLM_BASE_URL.rstrip("/")
        if provider == "groq":
            return "https://api.groq.com/openai/v1"
        if provider == "gemini":
            return "https://generativelanguage.googleapis.com/v1beta/openai"
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        return "https://api.openai.com/v1"

    @property
    def resolved_llm_model(self) -> str:
        """Resolve sensible default model based on provider if not explicitly overridden."""
        provider = self.LLM_PROVIDER.lower()
        if self.LLM_MODEL and self.LLM_MODEL not in ("gpt-4o-mini", "llama3.2"):
            return self.LLM_MODEL
        if provider == "ollama":
            return self.LLM_MODEL or "llama3.2"
        if provider == "groq":
            return "llama-3.3-70b-versatile"
        if provider == "gemini":
            return "gemini-1.5-flash"
        return self.LLM_MODEL or "llama3.2"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def is_testing(self) -> bool:
        return self.APP_ENV.lower() == "test"


@lru_cache
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
