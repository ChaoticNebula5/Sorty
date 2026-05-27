from pathlib import Path

import pytest

from app.services.local_storage_service import LocalStorageService


def test_local_storage_put_get_exists_and_delete(tmp_path: Path) -> None:
    storage = LocalStorageService(tmp_path)
    object_key = "events/event-id/originals/media-id.jpg"

    storage.put_bytes(object_key, b"image-bytes", "image/jpeg")

    assert storage.object_exists(object_key) is True
    assert storage.get_bytes(object_key) == b"image-bytes"

    storage.delete_object(object_key)

    assert storage.object_exists(object_key) is False


def test_local_storage_put_file(tmp_path: Path) -> None:
    storage = LocalStorageService(tmp_path / "storage")
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")

    storage.put_file("events/event-id/originals/source.txt", source, "text/plain")

    assert storage.get_bytes("events/event-id/originals/source.txt") == b"hello"


def test_local_storage_download_to_temp(tmp_path: Path) -> None:
    storage = LocalStorageService(tmp_path)
    storage.put_bytes("events/event-id/originals/media-id.jpg", b"image", "image/jpeg")

    temp_path = storage.download_to_temp("events/event-id/originals/media-id.jpg")

    try:
        assert temp_path.read_bytes() == b"image"
    finally:
        temp_path.unlink(missing_ok=True)


def test_local_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalStorageService(tmp_path)

    with pytest.raises(ValueError):
        storage.put_bytes("../secret.txt", b"nope", "text/plain")


def test_local_storage_rejects_windows_separators(tmp_path: Path) -> None:
    storage = LocalStorageService(tmp_path)

    with pytest.raises(ValueError):
        storage.put_bytes("events\\event-id\\file.jpg", b"nope", "image/jpeg")
