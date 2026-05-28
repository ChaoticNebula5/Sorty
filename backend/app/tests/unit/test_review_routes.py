import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_review import event_service, media_service, review_service
from app.core.config import get_settings
from app.main import app


def override_db() -> Generator[object, None, None]:
    yield object()


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().app_api_key}


def make_media(**overrides: object) -> SimpleNamespace:
    data = {
        "id": uuid.uuid4(),
        "event_id": uuid.uuid4(),
        "processing_status": "needs_review",
        "processing_error": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_analysis(**overrides: object) -> SimpleNamespace:
    data = {
        "caption": "A stage performance.",
        "tags": ["stage", "students"],
        "suggested_primary_folder": "Performances",
        "suggested_sub_folder": "Stage",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_decision(**overrides: object) -> SimpleNamespace:
    media = make_media()
    media.ai_analysis = make_analysis()
    media.quality_signal = None
    data = {
        "id": uuid.uuid4(),
        "media_id": media.id,
        "media": media,
        "status": "pending",
        "final_primary_folder": None,
        "final_sub_folder": None,
        "final_tags": [],
        "include_in_export": False,
        "review_reasons": ["low_confidence"],
        "reviewer_note": None,
        "reviewed_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_review_queue_requires_api_key() -> None:
    response = TestClient(app).get(f"/api/events/{uuid.uuid4()}/review-queue")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_review_queue_returns_items(monkeypatch) -> None:
    event_id = uuid.uuid4()
    decision = make_decision()

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(
        review_service,
        "list_event_review_queue",
        lambda db, event_id, limit=50, offset=0: [decision],
    )
    monkeypatch.setattr(review_service, "count_event_review_queue", lambda db, event_id: 1)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{event_id}/review-queue",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    item = body["data"][0]
    assert body["pagination"] == {"limit": 50, "offset": 0, "total": 1}
    assert item["media_id"] == str(decision.media.id)
    assert item["thumbnail_url"] == f"/api/media/{decision.media.id}/thumbnail"
    assert item["caption"] == "A stage performance."
    assert item["tags"] == ["stage", "students"]
    assert item["review_reasons"] == ["low_confidence"]
    assert item["current_review_status"] == "pending"


def test_review_queue_returns_404_for_missing_event(monkeypatch) -> None:
    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{uuid.uuid4()}/review-queue",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"


def test_update_media_review_requires_final_folder_for_approved() -> None:
    response = TestClient(app).patch(
        f"/api/media/{uuid.uuid4()}/review",
        headers=auth_headers(),
        json={"status": "approved", "include_in_export": True},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_update_media_review_requires_api_key() -> None:
    response = TestClient(app).patch(
        f"/api/media/{uuid.uuid4()}/review",
        json={"status": "rejected", "include_in_export": False},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_update_media_review_rejects_contradictory_export_decision() -> None:
    response = TestClient(app).patch(
        f"/api/media/{uuid.uuid4()}/review",
        headers=auth_headers(),
        json={"status": "rejected", "include_in_export": True},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_update_media_review_rejects_overlong_folder() -> None:
    response = TestClient(app).patch(
        f"/api/media/{uuid.uuid4()}/review",
        headers=auth_headers(),
        json={
            "status": "approved",
            "final_primary_folder": "x" * 121,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_update_media_review_returns_404_for_missing_media(monkeypatch) -> None:
    monkeypatch.setattr(media_service, "get_media_asset", lambda db, media_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).patch(
            f"/api/media/{uuid.uuid4()}/review",
            headers=auth_headers(),
            json={
                "status": "rejected",
                "include_in_export": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "media_not_found"


def test_update_media_review_returns_404_for_missing_decision(monkeypatch) -> None:
    media = make_media()

    monkeypatch.setattr(media_service, "get_media_asset", lambda db, media_id: media)
    monkeypatch.setattr(
        review_service,
        "get_review_decision_for_media",
        lambda db, media_id: None,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).patch(
            f"/api/media/{media.id}/review",
            headers=auth_headers(),
            json={
                "status": "rejected",
                "include_in_export": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "review_decision_not_found"


def test_update_media_review_returns_decision(monkeypatch) -> None:
    media = make_media()
    decision = make_decision(media=media, media_id=media.id)

    def fake_apply_review_decision(db, decision, payload):
        decision.status = payload.status
        decision.final_primary_folder = payload.final_primary_folder
        decision.final_sub_folder = payload.final_sub_folder
        decision.final_tags = payload.final_tags
        decision.include_in_export = payload.include_in_export
        decision.reviewer_note = payload.reviewer_note
        return decision

    monkeypatch.setattr(media_service, "get_media_asset", lambda db, media_id: media)
    monkeypatch.setattr(
        review_service,
        "get_review_decision_for_media",
        lambda db, media_id: decision,
    )
    monkeypatch.setattr(review_service, "apply_review_decision", fake_apply_review_decision)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).patch(
            f"/api/media/{media.id}/review",
            headers=auth_headers(),
            json={
                "status": "edited",
                "final_primary_folder": "Performances",
                "final_sub_folder": "Stage",
                "final_tags": ["stage", "students"],
                "include_in_export": True,
                "reviewer_note": "Good image for PR.",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["media_id"] == str(media.id)
    assert body["data"]["status"] == "edited"
    assert body["data"]["final_primary_folder"] == "Performances"
    assert body["data"]["include_in_export"] is True


def test_bulk_approve_reviews_requires_api_key() -> None:
    response = TestClient(app).post(
        f"/api/events/{uuid.uuid4()}/review/bulk-approve",
        json={"media_ids": [str(uuid.uuid4())]},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_bulk_approve_reviews_rejects_duplicate_media_ids() -> None:
    media_id = uuid.uuid4()

    response = TestClient(app).post(
        f"/api/events/{uuid.uuid4()}/review/bulk-approve",
        headers=auth_headers(),
        json={"media_ids": [str(media_id), str(media_id)]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_bulk_approve_reviews_returns_404_for_missing_event(monkeypatch) -> None:
    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{uuid.uuid4()}/review/bulk-approve",
            headers=auth_headers(),
            json={"media_ids": [str(uuid.uuid4())]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"


def test_bulk_approve_reviews_returns_conflict_for_invalid_items(monkeypatch) -> None:
    event_id = uuid.uuid4()
    media_id = uuid.uuid4()

    def fake_bulk_approve_pending_reviews(db, event_id, media_ids, reviewer_note=None):
        raise ValueError("All media_ids must belong to pending review items for this event.")

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(
        review_service,
        "bulk_approve_pending_reviews",
        fake_bulk_approve_pending_reviews,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/review/bulk-approve",
            headers=auth_headers(),
            json={"media_ids": [str(media_id)]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "bulk_approve_invalid_items"


def test_bulk_approve_reviews_returns_approved_summary(monkeypatch) -> None:
    event_id = uuid.uuid4()
    media_id = uuid.uuid4()
    media = make_media(id=media_id, event_id=event_id)
    decision = make_decision(media=media, media_id=media_id, status="approved")

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(
        review_service,
        "bulk_approve_pending_reviews",
        lambda db, event_id, media_ids, reviewer_note=None: [decision],
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/events/{event_id}/review/bulk-approve",
            headers=auth_headers(),
            json={
                "media_ids": [str(media_id)],
                "reviewer_note": "Looks good.",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"] == {
        "event_id": str(event_id),
        "approved_count": 1,
        "media_ids": [str(media_id)],
    }
