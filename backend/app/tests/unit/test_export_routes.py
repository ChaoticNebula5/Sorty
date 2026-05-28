import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_export import event_service, export_service, storage_factory
from app.core.config import get_settings
from app.main import app


def override_db() -> Generator[object, None, None]:
    yield object()


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().app_api_key}


def make_export_job(**overrides: object) -> SimpleNamespace:
    export_id = uuid.uuid4()
    data = {
        "id": export_id,
        "event_id": uuid.uuid4(),
        "status": "completed",
        "export_type": "organized_zip",
        "included_count": 2,
        "excluded_count": 1,
        "include_duplicates": False,
        "include_blurry": True,
        "include_pending": False,
        "zip_object_key": f"events/event-id/exports/{export_id}.zip",
        "error_message": None,
        "created_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_create_export_requires_api_key() -> None:
    response = TestClient(app).post(f"/api/events/{uuid.uuid4()}/export", json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_create_export_returns_404_for_missing_event(monkeypatch) -> None:
    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{uuid.uuid4()}/export",
            headers=auth_headers(),
            json={},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"


def test_create_export_returns_conflict_when_blocked(monkeypatch) -> None:
    event_id = uuid.uuid4()

    def fake_create_and_generate_export(db, event, payload, storage):
        raise export_service.ExportBlockedError("Export is blocked while review items are pending.")

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: object())
    monkeypatch.setattr(export_service, "create_and_generate_export", fake_create_and_generate_export)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/export",
            headers=auth_headers(),
            json={},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "export_blocked"


def test_create_export_returns_completed_job(monkeypatch) -> None:
    event_id = uuid.uuid4()
    export_job = make_export_job(event_id=event_id)

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: object())
    monkeypatch.setattr(
        export_service,
        "create_and_generate_export",
        lambda db, event, payload, storage: export_job,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/export",
            headers=auth_headers(),
            json={"include_duplicates": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == str(export_job.id)
    assert body["data"]["download_url"] == f"/api/exports/{export_job.id}/download"


def test_download_export_returns_conflict_when_not_ready(monkeypatch) -> None:
    export_job = make_export_job(status="exporting", zip_object_key=None)

    monkeypatch.setattr(export_service, "get_export_job", lambda db, export_id: export_job)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/exports/{export_job.id}/download",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "export_not_ready"


def test_download_export_streams_zip(monkeypatch) -> None:
    export_job = make_export_job()
    storage = SimpleNamespace(get_bytes=lambda object_key: b"zip-bytes")

    monkeypatch.setattr(export_service, "get_export_job", lambda db, export_id: export_job)
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: storage)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/exports/{export_job.id}/download",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content == b"zip-bytes"
