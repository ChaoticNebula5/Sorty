import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_public import event_service, media_service, storage_factory
from app.main import app


def override_db() -> Generator[object, None, None]:
    yield object()


def make_public_event(**overrides: object) -> SimpleNamespace:
    data = {
        "id": uuid.uuid4(),
        "name": "Public Fest",
        "event_type": "cultural",
        "description": "A published event.",
        "event_date": None,
        "is_public": True,
        "public_slug": "public-fest",
        "published_at": datetime.now(UTC),
        "archived_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_public_media(**overrides: object) -> SimpleNamespace:
    media_id = uuid.uuid4()
    data = {
        "id": media_id,
        "event_id": uuid.uuid4(),
        "thumbnail_object_key": f"events/event-id/thumbnails/{media_id}.jpg",
        "original_object_key": f"events/event-id/originals/{media_id}.jpg",
        "original_filename": "secret-original-name.jpg",
        "batch_job_id": uuid.uuid4(),
        "processing_status": "processed",
        "processing_error": "should not leak",
        "ai_analysis": SimpleNamespace(
            caption="A stage performance.",
            tags=["stage", "students"],
        ),
        "review_decision": SimpleNamespace(
            status="approved",
            final_tags=["featured"],
            include_in_export=True,
            review_reasons=["low_confidence"],
            reviewer_note="internal note",
        ),
        "quality_signal": SimpleNamespace(quality_label="sharp"),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_public_unpublished_event_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(
        event_service,
        "get_public_event_by_slug",
        lambda db, public_slug: None,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get("/api/public/events/draft-event")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "public_event_not_found"


def test_public_published_event_returns_safe_fields(monkeypatch) -> None:
    event = make_public_event()

    monkeypatch.setattr(
        event_service,
        "get_public_event_by_slug",
        lambda db, public_slug: event,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(f"/api/public/events/{event.public_slug}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["name"] == "Public Fest"
    assert body["data"]["public_slug"] == "public-fest"
    assert set(body["data"]) == {
        "name",
        "event_type",
        "description",
        "event_date",
        "public_slug",
        "published_at",
    }


def test_unpublishing_removes_public_access(monkeypatch) -> None:
    monkeypatch.setattr(
        event_service,
        "get_public_event_by_slug",
        lambda db, public_slug: None,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get("/api/public/events/public-fest")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_public_media_returns_only_safe_export_ready_fields(monkeypatch) -> None:
    event = make_public_event()
    media = make_public_media(event_id=event.id)

    monkeypatch.setattr(
        event_service,
        "get_public_event_by_slug",
        lambda db, public_slug: event,
    )
    monkeypatch.setattr(
        media_service,
        "list_public_event_media",
        lambda db, event_id, limit=50, offset=0: [media],
    )
    monkeypatch.setattr(media_service, "count_public_event_media", lambda db, event_id: 1)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(f"/api/public/events/{event.public_slug}/media")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    item = body["data"][0]
    assert body["pagination"] == {"limit": 50, "offset": 0, "total": 1}
    assert item == {
        "media_id": str(media.id),
        "thumbnail_url": (
            f"/api/public/events/{event.public_slug}/media/{media.id}/thumbnail"
        ),
        "caption": None,
        "tags": ["featured"],
        "quality_label": "sharp",
    }


def test_public_thumbnail_streams_export_ready_media(monkeypatch) -> None:
    event = make_public_event()
    media = make_public_media(event_id=event.id)
    storage = SimpleNamespace(
        object_exists=lambda object_key: True,
        get_bytes=lambda object_key: b"thumbnail-bytes",
    )

    monkeypatch.setattr(
        event_service,
        "get_public_event_by_slug",
        lambda db, public_slug: event,
    )
    monkeypatch.setattr(
        media_service,
        "get_public_event_media",
        lambda db, event_id, media_id: media,
    )
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: storage)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/public/events/{event.public_slug}/media/{media.id}/thumbnail",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.content == b"thumbnail-bytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert media.thumbnail_object_key not in str(response.headers)
    assert media.original_object_key not in str(response.headers)


def test_public_thumbnail_returns_404_when_thumbnail_object_missing(monkeypatch) -> None:
    event = make_public_event()
    media = make_public_media(event_id=event.id)
    storage = SimpleNamespace(object_exists=lambda object_key: False)

    monkeypatch.setattr(
        event_service,
        "get_public_event_by_slug",
        lambda db, public_slug: event,
    )
    monkeypatch.setattr(
        media_service,
        "get_public_event_media",
        lambda db, event_id, media_id: media,
    )
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: storage)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/public/events/{event.public_slug}/media/{media.id}/thumbnail",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "public_media_not_found"


def test_public_thumbnail_cannot_leak_private_media_by_uuid(monkeypatch) -> None:
    event = make_public_event()
    private_media_id = uuid.uuid4()

    monkeypatch.setattr(
        event_service,
        "get_public_event_by_slug",
        lambda db, public_slug: event,
    )
    monkeypatch.setattr(
        media_service,
        "get_public_event_media",
        lambda db, event_id, media_id: None,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/public/events/{event.public_slug}/media/{private_media_id}/thumbnail",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "public_media_not_found"
