from types import SimpleNamespace

import pytest

from app.services.minio_storage_service import MinioStorageService


class FakeMinioClient:
    def __init__(self) -> None:
        self.stat_calls: list[tuple[str, str]] = []
        self.presigned_calls: list[tuple[str, str, object]] = []

    def bucket_exists(self, bucket_name: str) -> bool:
        return True

    def stat_object(self, bucket_name: str, object_key: str) -> None:
        self.stat_calls.append((bucket_name, object_key))

    def presigned_get_object(self, bucket_name: str, object_key: str, expires: object) -> str:
        self.presigned_calls.append((bucket_name, object_key, expires))
        return "http://example.test/presigned"


def make_service(monkeypatch) -> MinioStorageService:
    fake_client = FakeMinioClient()

    def fake_minio(*args: object, **kwargs: object) -> FakeMinioClient:
        return fake_client

    monkeypatch.setattr("app.services.minio_storage_service.Minio", fake_minio)

    settings = SimpleNamespace(
        minio_bucket="sorty-media",
        minio_presigned_url_expiry_seconds=3600,
        minio_endpoint="minio:9000",
        minio_access_key="sortyadmin",
        minio_secret_key="sortypassword",
        minio_secure=False,
    )
    return MinioStorageService(settings)


def test_minio_storage_validates_object_key_before_stat(monkeypatch) -> None:
    service = make_service(monkeypatch)

    with pytest.raises(ValueError):
        service.object_exists("../secret.jpg")


def test_minio_storage_rejects_non_positive_presigned_expiry(monkeypatch) -> None:
    service = make_service(monkeypatch)

    with pytest.raises(ValueError):
        service.presigned_get_url("events/event-id/file.jpg", expires_seconds=0)


def test_minio_storage_uses_valid_presigned_expiry(monkeypatch) -> None:
    service = make_service(monkeypatch)

    url = service.presigned_get_url("events/event-id/file.jpg", expires_seconds=60)

    assert url == "http://example.test/presigned"
