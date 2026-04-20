"""
Storage abstraction layer for local filesystem and S3.
Handles both original files and thumbnails.
Optimized for local-first development.
"""

from pathlib import Path
import shutil
import aiofiles
import boto3
from botocore.exceptions import ClientError
from backend.config import settings


class StorageBackend:
    """Abstract storage interface."""

    async def put(self, file_bytes: bytes, file_hash: str, extension: str) -> str:
        """Store original file and return storage key."""
        raise NotImplementedError

    async def put_thumbnail(self, file_bytes: bytes, file_hash: str) -> str:
        """Store thumbnail and return storage key (always .jpg)."""
        raise NotImplementedError

    async def put_bytes(self, file_bytes: bytes, storage_key: str) -> str:
        """Store arbitrary bytes at a specific storage key."""
        raise NotImplementedError

    async def put_file(self, file_path: str, storage_key: str) -> str:
        """Store a file from disk at a specific storage key."""
        raise NotImplementedError

    async def get(self, storage_key: str) -> bytes:
        """Retrieve file by storage key."""
        raise NotImplementedError

    async def delete(self, storage_key: str) -> bool:
        """Delete file by storage key."""
        raise NotImplementedError

    def get_url(self, storage_key: str) -> str:
        """Get URL for accessing the file."""
        raise NotImplementedError

    def get_thumbnail_key(self, storage_key: str) -> str:
        """Get thumbnail key from original storage key."""
        # Thumbnail key: thumb_{file_hash}.jpg
        file_hash = storage_key.split(".")[0]
        return f"thumb_{file_hash}.jpg"


class LocalStorage(StorageBackend):
    """Local filesystem storage."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def put(self, file_bytes: bytes, file_hash: str, extension: str) -> str:
        """Store original file locally. Storage key includes extension."""
        storage_key = f"{file_hash}{extension}"
        file_path = self.base_path / storage_key

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)

        return storage_key

    async def put_thumbnail(self, file_bytes: bytes, file_hash: str) -> str:
        """Store thumbnail locally as thumb_{hash}.jpg."""
        storage_key = f"thumb_{file_hash}.jpg"
        file_path = self.base_path / storage_key

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)

        return storage_key

    async def put_bytes(self, file_bytes: bytes, storage_key: str) -> str:
        """Store arbitrary bytes locally with an explicit storage key."""
        file_path = self.base_path / storage_key
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)

        return storage_key

    async def put_file(self, file_path: str, storage_key: str) -> str:
        """Store a file from disk locally with an explicit storage key."""
        destination = self.base_path / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file_path, destination)
        return storage_key

    async def get(self, storage_key: str) -> bytes:
        """Retrieve file from local storage."""
        file_path = self.base_path / storage_key

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {storage_key}")

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def delete(self, storage_key: str) -> bool:
        """Delete file from local storage."""
        file_path = self.base_path / storage_key

        try:
            file_path.unlink()
            return True
        except FileNotFoundError:
            return False

    def get_url(self, storage_key: str) -> str:
        """Return relative URL for local files."""
        return f"/storage/{storage_key}"


class S3Storage(StorageBackend):
    """S3-compatible object storage (minimal, optional)."""

    def __init__(
        self,
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
        endpoint_url: str | None = None,
    ):
        self.bucket = bucket
        # Note: boto3 is sync; these methods are async for interface consistency but don't use asyncio internally
        self.s3_client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint_url,
        )

    async def put(self, file_bytes: bytes, file_hash: str, extension: str) -> str:
        """Upload original file to S3. Storage key includes extension."""
        storage_key = f"{file_hash}{extension}"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket, Key=storage_key, Body=file_bytes
            )
            return storage_key
        except ClientError as e:
            raise RuntimeError(f"S3 upload failed: {e}")

    async def put_thumbnail(self, file_bytes: bytes, file_hash: str) -> str:
        """Upload thumbnail to S3 as thumb_{hash}.jpg."""
        storage_key = f"thumb_{file_hash}.jpg"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=storage_key,
                Body=file_bytes,
                ContentType="image/jpeg",
            )
            return storage_key
        except ClientError as e:
            raise RuntimeError(f"S3 thumbnail upload failed: {e}")

    async def put_bytes(self, file_bytes: bytes, storage_key: str) -> str:
        """Upload arbitrary bytes to S3 at an explicit storage key."""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket, Key=storage_key, Body=file_bytes
            )
            return storage_key
        except ClientError as e:
            raise RuntimeError(f"S3 upload failed: {e}")

    async def put_file(self, file_path: str, storage_key: str) -> str:
        """Upload a file from disk to S3 at an explicit storage key."""
        try:
            self.s3_client.upload_file(file_path, self.bucket, storage_key)
            return storage_key
        except ClientError as e:
            raise RuntimeError(f"S3 upload failed: {e}")

    async def get(self, storage_key: str) -> bytes:
        """Download file from S3."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=storage_key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {storage_key}")
            raise RuntimeError(f"S3 download failed: {e}")

    async def delete(self, storage_key: str) -> bool:
        """Delete file from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=storage_key)
            return True
        except ClientError:
            return False

    def get_url(self, storage_key: str) -> str:
        """Generate S3 URL (assumes public bucket)."""
        return f"https://{self.bucket}.s3.amazonaws.com/{storage_key}"


def _create_storage() -> StorageBackend:
    """Create storage backend based on configuration."""
    if settings.is_local_storage:
        return LocalStorage(settings.local_storage_path)
    else:
        # S3 support is minimal/optional
        assert settings.s3_bucket is not None
        assert settings.s3_region is not None
        assert settings.s3_access_key is not None
        assert settings.s3_secret_key is not None

        return S3Storage(
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            endpoint_url=settings.s3_endpoint_url,
        )


# Global storage singleton
_storage_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Get storage singleton instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = _create_storage()
    return _storage_instance


# Convenience alias
storage = get_storage()
