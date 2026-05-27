import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from app.api.deps import get_db
from app.api.routes_media import (
    event_service,
    media_service,
    storage_factory,
)
from app.core.config import get_settings
from app.main import app
from app.services.thumbnail_service import ThumbnailError
from app.services.upload_validation_service import UploadValidationError


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, str]] = []
        self.deletes: list[str] = []

    def put_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        self.puts.append((object_key, data, content_type))

    def delete_object(self, object_key: str) -> None:
        self.deletes.append(object_key)


class FailingStorage(FakeStorage):
    def __init__(self, fail_on_put_number: int) -> None:
        super().__init__()
        self.fail_on_put_number = fail_on_put_number

    def put_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        if len(self.puts) + 1 == self.fail_on_put_number:
            raise RuntimeError("storage failed")
        super().put_bytes(object_key, data, content_type)


class FakeDb:
    def __init__(self) -> None:
        self.deleted: list[object] = []
        self.committed = False

    def delete(self, item: object) -> None:
        self.deleted.append(item)

    def commit(self) -> None:
        self.committed = True


def override_db() -> Generator[object, None, None]:
    yield object()


def override_fake_db(fake_db: FakeDb):
    def dependency() -> Generator[FakeDb, None, None]:
        yield fake_db

    return dependency


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().app_api_key}


def make_image_bytes() -> bytes:
    image = Image.new("RGB", (20, 10), color="green")
    output = BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def make_media(**overrides: object) -> SimpleNamespace:
    media_id = uuid.uuid4()
    event_id = uuid.uuid4()
    now = datetime.now(UTC)
    data = {
        "id": media_id,
        "event_id": event_id,
        "batch_job_id": None,
        "original_filename": "photo.jpg",
        "stored_filename": f"{media_id}.jpg",
        "bucket_name": "sorty-media",
        "original_object_key": f"events/{event_id}/originals/{media_id}.jpg",
        "thumbnail_object_key": f"events/{event_id}/thumbnails/{media_id}.jpg",
        "mime_type": "image/jpeg",
        "file_extension": ".jpg",
        "size_bytes": 123,
        "upload_status": "accepted",
        "processing_status": "uploaded",
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_batch_upload_requires_api_key() -> None:
    response = TestClient(app).post(
        f"/api/events/{uuid.uuid4()}/media/batch-upload",
        files=[],
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_batch_upload_rejects_missing_event(monkeypatch) -> None:
    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{uuid.uuid4()}/media/batch-upload",
            headers=auth_headers(),
            files=[("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"


def test_batch_upload_accepts_valid_file(monkeypatch) -> None:
    event_id = uuid.uuid4()
    media = make_media(event_id=event_id)
    storage = FakeStorage()

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(media_service, "create_media_asset", lambda db, payload: media)
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: storage)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/media/batch-upload",
            headers=auth_headers(),
            files=[("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    assert body["data"]["accepted_count"] == 1
    assert body["data"]["rejected_count"] == 0
    assert body["data"]["media_ids"] == [str(media.id)]
    assert len(storage.puts) == 2


def test_batch_upload_returns_rejected_file_for_validation_error(monkeypatch) -> None:
    def fake_validate_upload(filename: str, content_type: str | None, data: bytes):
        raise UploadValidationError("invalid_image", "Invalid image.")

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr("app.api.routes_media.validate_upload", fake_validate_upload)
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: FakeStorage())
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{uuid.uuid4()}/media/batch-upload",
            headers=auth_headers(),
            files=[("files", ("bad.jpg", b"not-image", "image/jpeg"))],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["accepted_count"] == 0
    assert body["data"]["rejected_count"] == 1
    assert body["data"]["rejected_files"][0]["code"] == "invalid_image"


def test_batch_upload_thumbnail_failure_does_not_create_media(monkeypatch) -> None:
    def fake_generate_thumbnail_jpeg(data: bytes) -> bytes:
        raise ThumbnailError("thumbnail failed")

    created_payloads = []

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr("app.api.routes_media.generate_thumbnail_jpeg", fake_generate_thumbnail_jpeg)
    monkeypatch.setattr(
        media_service,
        "create_media_asset",
        lambda db, payload: created_payloads.append(payload),
    )
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: FakeStorage())
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{uuid.uuid4()}/media/batch-upload",
            headers=auth_headers(),
            files=[("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["accepted_count"] == 0
    assert body["data"]["rejected_files"][0]["code"] == "thumbnail_failed"
    assert created_payloads == []


def test_batch_upload_storage_failure_cleans_up_media(monkeypatch) -> None:
    event_id = uuid.uuid4()
    media = make_media(event_id=event_id)
    storage = FailingStorage(fail_on_put_number=2)
    fake_db = FakeDb()

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(media_service, "create_media_asset", lambda db, payload: media)
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: storage)
    app.dependency_overrides[get_db] = override_fake_db(fake_db)

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/media/batch-upload",
            headers=auth_headers(),
            files=[("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["accepted_count"] == 0
    assert body["data"]["rejected_files"][0]["code"] == "storage_failed"
    assert storage.deletes == [media.original_object_key, media.thumbnail_object_key]
    assert fake_db.deleted == [media]
    assert fake_db.committed is True


def test_batch_upload_first_storage_write_failure_cleans_up_media(monkeypatch) -> None:
    event_id = uuid.uuid4()
    media = make_media(event_id=event_id)
    storage = FailingStorage(fail_on_put_number=1)
    fake_db = FakeDb()

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(media_service, "create_media_asset", lambda db, payload: media)
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: storage)
    app.dependency_overrides[get_db] = override_fake_db(fake_db)

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/media/batch-upload",
            headers=auth_headers(),
            files=[("files", ("photo.jpg", make_image_bytes(), "image/jpeg"))],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["accepted_count"] == 0
    assert body["data"]["rejected_files"][0]["code"] == "storage_failed"
    assert storage.deletes == [media.original_object_key, media.thumbnail_object_key]
    assert fake_db.deleted == [media]
    assert fake_db.committed is True


def test_list_event_media_returns_items(monkeypatch) -> None:
    event_id = uuid.uuid4()
    media = make_media(event_id=event_id)

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(
        media_service,
        "list_event_media",
        lambda db, event_id, limit=50, offset=0: [media],
    )
    monkeypatch.setattr(media_service, "count_event_media", lambda db, event_id: 1)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{event_id}/media",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["pagination"] == {"limit": 50, "offset": 0, "total": 1}
    assert body["data"][0]["id"] == str(media.id)
    assert body["data"][0]["thumbnail_url"] == f"/api/media/{media.id}/thumbnail"


def test_get_media_returns_item(monkeypatch) -> None:
    media = make_media()

    monkeypatch.setattr(media_service, "get_media_asset", lambda db, media_id: media)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/media/{media.id}",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["id"] == str(media.id)
    assert body["data"]["file_url"] == f"/api/media/{media.id}/file"


def test_get_media_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(media_service, "get_media_asset", lambda db, media_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/media/{uuid.uuid4()}",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "media_not_found"
