import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_events import event_service, job_service, media_service
from app.core.config import get_settings
from app.main import app


def override_db() -> Generator[object, None, None]:
    yield object()


def make_event(**overrides: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    data = {
        "id": uuid.uuid4(),
        "name": "Cultural Fest 2026",
        "slug": "cultural-fest-2026",
        "event_type": "cultural",
        "description": "Annual cultural event",
        "event_date": None,
        "created_at": now,
        "updated_at": now,
        "archived_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_job(**overrides: object) -> SimpleNamespace:
    now = datetime.now(UTC)
    data = {
        "id": uuid.uuid4(),
        "event_id": uuid.uuid4(),
        "current_rq_job_id": "rq-job-id",
        "status": "queued",
        "total_files": 2,
        "processed_files": 0,
        "failed_files": 0,
        "needs_review_count": 0,
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().admin_token}"}


def admin_headers() -> dict[str, str]:
    return auth_headers()


def test_list_events_requires_api_key() -> None:
    response = TestClient(app).get("/api/events")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_admin_token"


def test_list_events_rejects_invalid_api_key() -> None:
    response = TestClient(app).get(
        "/api/events",
        headers={"Authorization": "Bearer wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_admin_token"


def test_create_event_returns_created_event(monkeypatch) -> None:
    event = make_event()

    def fake_create_event(db: object, payload: object) -> SimpleNamespace:
        return event

    monkeypatch.setattr(event_service, "create_event", fake_create_event)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            "/api/events",
            headers=auth_headers(),
            json={
                "name": "Cultural Fest 2026",
                "event_type": "cultural",
                "description": "Annual cultural event",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == str(event.id)
    assert body["data"]["name"] == "Cultural Fest 2026"
    assert body["data"]["slug"] == "cultural-fest-2026"


def test_create_event_accepts_admin_bearer_token(monkeypatch) -> None:
    event = make_event()

    monkeypatch.setattr(event_service, "create_event", lambda db, payload: event)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            "/api/events",
            headers=admin_headers(),
            json={"name": "Cultural Fest 2026"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["data"]["id"] == str(event.id)


def test_create_event_returns_wrapped_validation_error() -> None:
    response = TestClient(app).post(
        "/api/events",
        headers=auth_headers(),
        json={"name": "A"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "validation_error"


def test_list_events_returns_pagination(monkeypatch) -> None:
    event = make_event()

    def fake_list_events(
        db: object,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SimpleNamespace], int]:
        return [event], 1

    monkeypatch.setattr(event_service, "list_events", fake_list_events)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get("/api/events", headers=auth_headers())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["pagination"] == {"limit": 50, "offset": 0, "total": 1}
    assert body["data"][0]["id"] == str(event.id)


def test_get_event_returns_404_for_missing_event(monkeypatch) -> None:
    def fake_get_event(db: object, event_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(event_service, "get_event", fake_get_event)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{uuid.uuid4()}",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"


def test_get_event_returns_wrapped_validation_error_for_invalid_uuid() -> None:
    response = TestClient(app).get(
        "/api/events/not-a-uuid",
        headers=auth_headers(),
    )

    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "validation_error"


def test_get_event_returns_event(monkeypatch) -> None:
    event = make_event()

    def fake_get_event(db: object, event_id: uuid.UUID) -> SimpleNamespace:
        return event

    monkeypatch.setattr(event_service, "get_event", fake_get_event)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{event.id}",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == str(event.id)
    assert body["data"]["slug"] == "cultural-fest-2026"


def test_admin_can_publish_event(monkeypatch) -> None:
    event_id = uuid.uuid4()
    published_at = datetime.now(UTC)
    event = make_event(
        id=event_id,
        is_public=True,
        public_slug="public-fest",
        published_at=published_at,
    )
    captured_payload = {}

    def fake_update_event_public_settings(db, event, payload):
        captured_payload["is_public"] = payload.is_public
        captured_payload["public_slug"] = payload.public_slug
        return event

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: event)
    monkeypatch.setattr(
        event_service,
        "update_event_public_settings",
        fake_update_event_public_settings,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).patch(
            f"/api/events/{event_id}/public",
            headers=admin_headers(),
            json={"is_public": True, "public_slug": "public-fest"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["is_public"] is True
    assert body["data"]["public_slug"] == "public-fest"
    assert body["data"]["published_at"] is not None
    assert captured_payload == {"is_public": True, "public_slug": "public-fest"}


def test_publish_rejects_duplicate_custom_slug(monkeypatch) -> None:
    event = make_event()

    def fake_update_event_public_settings(db, event, payload):
        raise ValueError("public_slug is already in use.")

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: event)
    monkeypatch.setattr(
        event_service,
        "update_event_public_settings",
        fake_update_event_public_settings,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).patch(
            f"/api/events/{event.id}/public",
            headers=admin_headers(),
            json={"is_public": True, "public_slug": "taken-slug"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "public_slug_conflict"


def test_admin_can_unpublish_event(monkeypatch) -> None:
    event = make_event(is_public=False, public_slug="public-fest", published_at=None)

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: event)
    monkeypatch.setattr(
        event_service,
        "update_event_public_settings",
        lambda db, event, payload: event,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).patch(
            f"/api/events/{event.id}/public",
            headers=admin_headers(),
            json={"is_public": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["is_public"] is False
    assert body["data"]["published_at"] is None


def test_list_event_jobs_requires_api_key() -> None:
    response = TestClient(app).get(f"/api/events/{uuid.uuid4()}/jobs")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_admin_token"


def test_get_event_media_summary_returns_counts(monkeypatch) -> None:
    event = make_event()
    summary = media_service.EventMediaSummaryData(
        event_id=event.id,
        total_media=10,
        processed_media=6,
        needs_review_media=2,
        failed_media=1,
        blurry_media=2,
        possible_duplicate_media=1,
        pending_review_decisions=2,
        approved_review_decisions=5,
        edited_review_decisions=3,
        rejected_review_decisions=1,
        confirmed_duplicate_decisions=1,
        export_ready_review_decisions=7,
    )

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: event)
    monkeypatch.setattr(
        media_service,
        "get_event_media_summary",
        lambda db, event_id: summary,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{event.id}/media-summary",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["event_id"] == str(event.id)
    assert body["data"]["total_media"] == 10
    assert body["data"]["blurry_media"] == 2
    assert body["data"]["possible_duplicate_media"] == 1
    assert body["data"]["edited_review_decisions"] == 3
    assert body["data"]["export_ready_review_decisions"] == 7


def test_get_event_media_summary_returns_404_for_missing_event(monkeypatch) -> None:
    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{uuid.uuid4()}/media-summary",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"


def test_list_event_jobs_returns_pagination(monkeypatch) -> None:
    event = make_event()
    job = make_job(event_id=event.id)
    captured: dict[str, int] = {}

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: event)
    monkeypatch.setattr(
        job_service,
        "list_event_jobs",
        lambda db, event_id, limit=50, offset=0: captured.update(
            {"limit": limit, "offset": offset}
        )
        or [job],
    )
    monkeypatch.setattr(job_service, "count_event_jobs", lambda db, event_id: 1)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{event.id}/jobs?limit=10&offset=20",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["pagination"] == {"limit": 10, "offset": 20, "total": 1}
    assert captured == {"limit": 10, "offset": 20}
    assert body["data"][0]["id"] == str(job.id)
    assert body["data"][0]["status"] == "queued"


def test_list_event_jobs_rejects_invalid_pagination() -> None:
    event_id = uuid.uuid4()

    for query in ("limit=0", "limit=101", "offset=-1"):
        response = TestClient(app).get(
            f"/api/events/{event_id}/jobs?{query}",
            headers=auth_headers(),
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_list_event_jobs_returns_404_for_missing_event(monkeypatch) -> None:
    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{uuid.uuid4()}/jobs",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"
