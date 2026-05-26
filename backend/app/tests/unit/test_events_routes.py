import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_events import event_service
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


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().app_api_key}


def test_list_events_requires_api_key() -> None:
    response = TestClient(app).get("/api/events")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_list_events_rejects_invalid_api_key() -> None:
    response = TestClient(app).get("/api/events", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


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
