"""Application configuration using pydantic-settings"""
from functools import lru_cache
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import field_validator
import secrets
import logging

logger = logging.getLogger(__name__)

# Persistent development secret key - stable across restarts
# In production, this MUST be overridden via SECRET_KEY environment variable
_DEV_SECRET_KEY = "dev-secret-key-for-local-development-only-change-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "Title Search Application"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # API
    API_PREFIX: str = "/api"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./title_search.db"
    DATABASE_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # JWT Authentication
    # Uses persistent dev key for stability; override with SECRET_KEY env var in production
    SECRET_KEY: str = _DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Password Requirements
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True

    # Storage
    STORAGE_BACKEND: str = "local"  # local, s3, minio
    STORAGE_PATH: str = "./storage"
    S3_BUCKET: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_ENDPOINT: Optional[str] = None
    S3_REGION: str = "us-east-1"

    # File Upload Settings
    MAX_UPLOAD_SIZE_MB: int = 50  # Maximum file upload size in MB
    ALLOWED_UPLOAD_EXTENSIONS: str = ".pdf,.png,.jpg,.jpeg,.tiff,.tif"  # Comma-separated allowed extensions
    ALLOWED_UPLOAD_MIMETYPES: str = "application/pdf,image/png,image/jpeg,image/tiff"  # Comma-separated allowed MIME types

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_UPLOAD_EXTENSIONS.split(",")]

    @property
    def allowed_mimetypes_list(self) -> List[str]:
        return [mime.strip().lower() for mime in self.ALLOWED_UPLOAD_MIMETYPES.split(",")]

    # AI Providers
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DEFAULT_AI_PROVIDER: str = "openai"
    DEFAULT_AI_MODEL: str = "gpt-4-turbo-preview"

    # OCR
    TESSERACT_CMD: Optional[str] = None
    OCR_DPI: int = 300

    # AI Processing
    AI_TEXT_TRUNCATION_LIMIT: int = 15000  # Max chars to send to AI for analysis

    # Browser Automation
    BROWSER_HEADLESS: bool = True
    BROWSER_POOL_SIZE: int = 5
    BROWSER_TIMEOUT: int = 30000
    BROWSER_MAX_REQUESTS_PER_INSTANCE: int = 100  # Recycle browser after this many requests

    # Scraping Settings
    SCRAPING_MAX_RETRIES: int = 3
    SCRAPING_RETRY_DELAY_SECONDS: int = 120
    SCRAPING_RATE_LIMIT_DELAY_SECONDS: int = 60
    SCRAPING_DEFAULT_SEARCH_YEARS: int = 40

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # Reports
    REPORTS_FOLDER: str = "./reports"

    # Admin
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None

    # Email/SMTP Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True
    FROM_EMAIL: Optional[str] = None
    FROM_NAME: str = "Title Search Application"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        environment = info.data.get("ENVIRONMENT", "development")
        if environment == "production":
            if v == _DEV_SECRET_KEY:
                raise ValueError(
                    "SECRET_KEY must be set via environment variable in production. "
                    "Do not use the default development key."
                )
            if len(v) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production")
        elif v == _DEV_SECRET_KEY:
            logger.warning(
                "Using default development SECRET_KEY. This is fine for development, "
                "but MUST be overridden in production via the SECRET_KEY environment variable."
            )
        return v

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def parse_allowed_origins(cls, v: str) -> str:
        return v

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
