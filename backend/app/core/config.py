from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Sorty AI"
    app_env: str = "local"
    app_api_key: str = Field(default="demo-secret", min_length=1)

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    database_url: str = "postgresql+psycopg://sorty:sorty@postgres:5432/sorty"
    redis_url: str = "redis://redis:6379/0"

    storage_provider: Literal["minio", "local"] = "minio"
    storage_root: str = "/app/storage"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "sortyadmin"
    minio_secret_key: str = "sortypassword"
    minio_bucket: str = "sorty-media"
    minio_secure: bool = False
    minio_presigned_url_expiry_seconds: int = 3600

    max_upload_size_mb: int = 10
    thumbnail_size: int = 300

    vision_provider: Literal["mock", "gemini", "openai", "ollama"] = "mock"
    gemini_api_key: str = ""
    gemini_vision_model: str = "gemini-2.0-flash"
    openai_api_key: str = ""
    openai_vision_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://ollama:11434"
    ollama_vision_model: str = "llava"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    langgraph_auto_setup_checkpointer: bool = True

    rq_queue_name: str = "mediaops"
    job_poll_interval_seconds: int = 2

    blur_threshold_blurry: int = 80
    blur_threshold_acceptable: int = 150
    phash_duplicate_threshold: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
