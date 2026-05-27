from pathlib import Path
from types import SimpleNamespace

from app.services.local_storage_service import LocalStorageService
from app.services import storage_factory


def test_storage_factory_returns_local_service(tmp_path: Path) -> None:
    settings = SimpleNamespace(
        storage_provider="local",
        storage_root=str(tmp_path),
    )

    storage = storage_factory.get_storage_service(settings)

    assert isinstance(storage, LocalStorageService)


def test_storage_factory_returns_minio_service(monkeypatch) -> None:
    class FakeMinioStorageService:
        def __init__(self, settings: object) -> None:
            self.settings = settings

    settings = SimpleNamespace(storage_provider="minio")
    monkeypatch.setattr(
        storage_factory,
        "MinioStorageService",
        FakeMinioStorageService,
    )

    storage = storage_factory.get_storage_service(settings)

    assert isinstance(storage, FakeMinioStorageService)


def test_storage_factory_rejects_unknown_provider() -> None:
    settings = SimpleNamespace(storage_provider="unknown")

    try:
        storage_factory.get_storage_service(settings)
    except ValueError as exc:
        assert "Unsupported storage provider" in str(exc)
    else:
        raise AssertionError("Expected unsupported provider to raise ValueError.")
