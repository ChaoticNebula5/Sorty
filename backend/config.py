"""
Configuration management for Sorty backend.
All settings are loaded from environment variables via pydantic-settings.
"""

from typing import Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    See PRD section 5 for full environment variable reference.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # App
    app_env: Literal["development", "production"] = Field(
        default="development", description="Application environment"
    )
    debug: bool = Field(default=False, description="Debug mode")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://sorty:sorty@localhost:5432/sorty",
        description="PostgreSQL connection string with asyncpg driver",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for queue and cache",
    )

    # Storage
    storage_backend: Literal["local", "s3"] = Field(
        default="local", description="Storage backend type"
    )
    local_storage_path: str = Field(
        default="./backend/storage/uploads", description="Path for local file storage"
    )
    s3_bucket: str | None = Field(default=None, description="S3 bucket name")
    s3_region: str | None = Field(default=None, description="S3 region")
    s3_access_key: str | None = Field(default=None, description="S3 access key")
    s3_secret_key: str | None = Field(default=None, description="S3 secret key")
    s3_endpoint_url: str | None = Field(
        default=None,
        description="S3 endpoint URL for S3-compatible storage (e.g., MinIO)",
    )

    # AI - Gemini Vision API
    gemini_api_key: str | None = Field(
        default=None, description="Google Gemini API key for vision tasks"
    )
    gemini_vision_model: str = Field(
        default="gemini-1.5-flash", description="Gemini vision model name"
    )

    # Embeddings - CLIP
    clip_model_path: str = Field(
        default="./models/clip-vit-base-patch32",
        description="Path to CLIP model weights (local cache)",
    )

    # Processing
    worker_concurrency: int = Field(
        default=4, description="Number of concurrent workers for enrichment queue"
    )
    max_retries: int = Field(default=3, description="Max job retry attempts")
    retry_delays_seconds: list[int] = Field(
        default=[2, 4, 8], description="Retry delays in seconds for attempts 1, 2, 3"
    )

    # Export
    export_dir: str = Field(
        default="./backend/storage/exports",
        description="Directory for generated export ZIPs",
    )
    export_max_size_bytes: int = Field(
        default=2_147_483_648,  # 2GB
        description="Maximum export size in bytes",
    )
    export_link_ttl_seconds: int = Field(
        default=86400,  # 24 hours
        description="Export download link time-to-live",
    )

    # Upload constraints
    max_file_size_bytes: int = Field(
        default=10_485_760,  # 10MB
        description="Maximum upload file size in bytes",
    )
    max_files_per_upload: int = Field(
        default=50, description="Maximum number of files per upload request"
    )

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], description="Allowed CORS origins"
    )

    # Assistant
    max_assets_per_action: int = Field(
        default=100, description="Maximum assets returned/added per assistant action"
    )

    # Search
    default_search_limit: int = Field(
        default=50, description="Default search page size"
    )
    max_search_limit: int = Field(default=200, description="Maximum search page size")

    # Rate limiting
    rate_limit_upload_per_minute: int = Field(default=50)
    rate_limit_search_per_minute: int = Field(default=100)
    rate_limit_export_per_minute: int = Field(default=10)
    rate_limit_assistant_per_minute: int = Field(default=30)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse comma-separated CORS origins from env var or accept list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    @model_validator(mode="after")
    def validate_dependencies(self):
        """Validate configuration dependencies."""
        # S3 backend requires all S3 credentials
        if self.storage_backend == "s3":
            missing = []
            if not self.s3_bucket:
                missing.append("S3_BUCKET")
            if not self.s3_region:
                missing.append("S3_REGION")
            if not self.s3_access_key:
                missing.append("S3_ACCESS_KEY")
            if not self.s3_secret_key:
                missing.append("S3_SECRET_KEY")

            if missing:
                raise ValueError(
                    f"S3 storage backend selected but missing required config: {', '.join(missing)}"
                )

        # Production requires Gemini API key
        if self.app_env == "production" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when APP_ENV=production")

        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def is_local_storage(self) -> bool:
        """Check if using local file storage."""
        return self.storage_backend == "local"


# Global settings instance (singleton)
settings = Settings()
