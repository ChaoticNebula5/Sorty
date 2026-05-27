import tempfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.core.config import Settings
from app.services.object_keys import validate_object_key


class MinioStorageService:
    def __init__(self, settings: Settings) -> None:
        self.bucket_name = settings.minio_bucket
        self.default_expiry_seconds = settings.minio_presigned_url_expiry_seconds
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.ensure_bucket()

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def put_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        validate_object_key(object_key)
        self.client.put_object(
            self.bucket_name,
            object_key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def put_file(self, object_key: str, file_path: str | Path, content_type: str) -> None:
        validate_object_key(object_key)
        self.client.fput_object(
            self.bucket_name,
            object_key,
            str(file_path),
            content_type=content_type,
        )

    def get_bytes(self, object_key: str) -> bytes:
        validate_object_key(object_key)
        response = self.client.get_object(self.bucket_name, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def download_to_temp(self, object_key: str) -> Path:
        validate_object_key(object_key)
        suffix = Path(object_key).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)

        self.client.fget_object(self.bucket_name, object_key, str(temp_path))
        return temp_path

    def delete_object(self, object_key: str) -> None:
        validate_object_key(object_key)
        self.client.remove_object(self.bucket_name, object_key)

    def presigned_get_url(
        self,
        object_key: str,
        expires_seconds: int | None = None,
    ) -> str:
        validate_object_key(object_key)
        resolved_expires_seconds = (
            expires_seconds
            if expires_seconds is not None
            else self.default_expiry_seconds
        )
        if resolved_expires_seconds <= 0:
            raise ValueError("Presigned URL expiry must be positive.")

        expires = timedelta(seconds=resolved_expires_seconds)
        return self.client.presigned_get_object(
            self.bucket_name,
            object_key,
            expires=expires,
        )

    def object_exists(self, object_key: str) -> bool:
        validate_object_key(object_key)
        try:
            self.client.stat_object(self.bucket_name, object_key)
            return True
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                return False
            raise
