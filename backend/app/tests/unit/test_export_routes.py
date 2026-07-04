import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_export import (
    create_export_download_token,
    event_service,
    export_job_to_read,
    export_service,
    queue_service,
    storage_factory,
)
from app.core.config import get_settings
from app.main import app


def override_db() -> Generator[object, None, None]:
    yield object()


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().admin_token}"}


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
    assert response.json()["error"]["code"] == "missing_admin_token"


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

    def fake_create_export_job(db, event, payload):
        raise export_service.ExportBlockedError("Export is blocked while review items are pending.")

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(export_service, "create_export_job", fake_create_export_job)
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


def test_create_export_returns_queued_job(monkeypatch) -> None:
    event_id = uuid.uuid4()
    export_job = make_export_job(event_id=event_id, status="created")
    queued_job = make_export_job(id=export_job.id, event_id=event_id, status="queued")

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(
        export_service,
        "create_export_job",
        lambda db, event, payload: export_job,
    )
    monkeypatch.setattr(queue_service, "enqueue_export", lambda export_id: "rq-export-id")
    monkeypatch.setattr(
        export_service,
        "mark_export_queued",
        lambda db, export_job: queued_job,
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
    assert body["data"]["status"] == "queued"
    assert body["data"]["download_url"] is None


def test_completed_export_read_includes_scoped_download_token() -> None:
    export_job = make_export_job(status="completed")

    body = export_job_to_read(export_job)

    assert body.download_url is not None
    assert body.download_url.startswith(f"/api/exports/{export_job.id}/download?token=")
    assert get_settings().admin_token not in body.download_url


def test_create_export_marks_queued_before_enqueue(monkeypatch) -> None:
    event_id = uuid.uuid4()
    export_job = make_export_job(event_id=event_id, status="created")
    queued_job = make_export_job(id=export_job.id, event_id=event_id, status="queued")
    calls: list[str] = []

    def fake_mark_export_queued(db, export_job):
        calls.append("mark_queued")
        return queued_job

    def fake_enqueue_export(export_id):
        calls.append("enqueue")
        return "rq-export-id"

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(
        export_service,
        "create_export_job",
        lambda db, event, payload: export_job,
    )
    monkeypatch.setattr(export_service, "mark_export_queued", fake_mark_export_queued)
    monkeypatch.setattr(queue_service, "enqueue_export", fake_enqueue_export)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/export",
            headers=auth_headers(),
            json={},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert calls == ["mark_queued", "enqueue"]


def test_create_export_returns_503_when_queue_unavailable(monkeypatch) -> None:
    event_id = uuid.uuid4()
    export_job = make_export_job(event_id=event_id, status="created")
    failed: list[str] = []

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(
        export_service,
        "create_export_job",
        lambda db, event, payload: export_job,
    )
    monkeypatch.setattr(
        queue_service,
        "enqueue_export",
        lambda export_id: (_ for _ in ()).throw(RuntimeError("redis down")),
    )
    monkeypatch.setattr(
        export_service,
        "mark_export_queued",
        lambda db, export_job: export_job,
    )
    monkeypatch.setattr(
        export_service,
        "mark_export_failed",
        lambda db, export_job, error_message: failed.append(error_message),
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/export",
            headers=auth_headers(),
            json={},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "queue_unavailable"
    assert failed == ["Could not enqueue export job."]


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
    requested_keys: list[str] = []

    def fake_get_bytes(object_key: str) -> bytes:
        requested_keys.append(object_key)
        return b"zip-bytes"

    storage = SimpleNamespace(get_bytes=fake_get_bytes)

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
    assert response.headers["content-disposition"] == f'attachment; filename="{export_job.id}.zip"'
    assert response.headers["content-length"] == str(len(b"zip-bytes"))
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == b"zip-bytes"
    assert requested_keys == [export_job.zip_object_key]


def test_download_export_accepts_query_token_for_browser_download(monkeypatch) -> None:
    export_job = make_export_job()
    storage = SimpleNamespace(get_bytes=lambda object_key: b"zip-bytes")

    monkeypatch.setattr(export_service, "get_export_job", lambda db, export_id: export_job)
    monkeypatch.setattr(storage_factory, "get_storage_service", lambda: storage)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/exports/{export_job.id}/download",
            params={"token": create_export_download_token(export_job.id)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content == b"zip-bytes"


def test_download_export_rejects_missing_query_token(monkeypatch) -> None:
    export_job = make_export_job()

    monkeypatch.setattr(export_service, "get_export_job", lambda db, export_id: export_job)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(f"/api/exports/{export_job.id}/download")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_admin_token"


def test_download_export_rejects_invalid_query_token(monkeypatch) -> None:
    export_job = make_export_job()

    monkeypatch.setattr(export_service, "get_export_job", lambda db, export_id: export_job)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/exports/{export_job.id}/download",
            params={"token": "wrong"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_admin_token"
