from app.core.config import Settings, get_settings
from app.services.local_storage_service import LocalStorageService
from app.services.minio_storage_service import MinioStorageService
from app.services.storage_service import StorageService


def get_storage_service(settings: Settings | None = None) -> StorageService:
    resolved_settings = settings or get_settings()

    if resolved_settings.storage_provider == "local":
        return LocalStorageService(resolved_settings.storage_root)

    if resolved_settings.storage_provider == "minio":
        return MinioStorageService(resolved_settings)

    raise ValueError(f"Unsupported storage provider: {resolved_settings.storage_provider}")
