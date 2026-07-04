import uuid
from collections.abc import Generator
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_search import event_service, search_service
from app.core.config import get_settings
from app.main import app


def override_db() -> Generator[object, None, None]:
    yield object()


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().admin_token}"}


def make_media(**overrides: object) -> SimpleNamespace:
    media_id = uuid.uuid4()
    data = {
        "id": media_id,
        "original_filename": "stage.jpg",
        "ai_analysis": SimpleNamespace(
            caption="A stage performance.",
            tags=["stage", "students"],
            suggested_primary_folder="Performances",
            suggested_sub_folder="Stage",
        ),
        "review_decision": SimpleNamespace(
            status="approved",
            final_primary_folder="Highlights",
            final_sub_folder="Performances",
            final_tags=["featured"],
            include_in_export=True,
        ),
        "quality_signal": SimpleNamespace(quality_label="sharp", is_duplicate=False),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_search_requires_api_key() -> None:
    response = TestClient(app).get(
        f"/api/events/{uuid.uuid4()}/search",
        params={"q": "stage"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_admin_token"


def test_search_rejects_short_query() -> None:
    response = TestClient(app).get(
        f"/api/events/{uuid.uuid4()}/search",
        headers=auth_headers(),
        params={"q": "x"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_search_returns_404_for_missing_event(monkeypatch) -> None:
    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{uuid.uuid4()}/search",
            headers=auth_headers(),
            params={"q": "stage"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"


def test_search_returns_ranked_media(monkeypatch) -> None:
    event_id = uuid.uuid4()
    media = make_media()
    result = search_service.SearchResult(media=media, score=0.91)

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    captured_filters: list[search_service.SearchFilters] = []

    def fake_search_event_media(
        db,
        event_id,
        query,
        limit=20,
        offset=0,
        filters=None,
    ):
        captured_filters.append(filters)
        return [result]

    monkeypatch.setattr(search_service, "search_event_media", fake_search_event_media)
    monkeypatch.setattr(
        search_service,
        "count_searchable_event_media",
        lambda db, event_id, query=None, filters=None: 1,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{event_id}/search",
            headers=auth_headers(),
            params={"q": "stage"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    item = body["data"][0]
    assert body["pagination"] == {"limit": 20, "offset": 0, "total": 1}
    assert item["media_id"] == str(media.id)
    assert item["thumbnail_url"] == f"/api/media/{media.id}/thumbnail"
    assert item["file_url"] == f"/api/media/{media.id}/file"
    assert item["caption"] == "A stage performance."
    assert item["tags"] == ["featured"]
    assert item["primary_folder"] == "Highlights"
    assert item["review_status"] == "approved"
    assert item["include_in_export"] is True
    assert item["score"] == 0.91
    assert captured_filters == [search_service.SearchFilters()]


def test_search_passes_filter_params_to_service(monkeypatch) -> None:
    event_id = uuid.uuid4()
    captured: dict[str, object] = {}

    def fake_search_event_media(
        db,
        event_id,
        query,
        limit=20,
        offset=0,
        filters=None,
    ):
        captured["search"] = filters
        return []

    def fake_count_searchable_event_media(db, event_id, query=None, filters=None):
        captured["count_query"] = query
        captured["count"] = filters
        return 0

    monkeypatch.setattr(event_service, "get_event", lambda db, event_id: object())
    monkeypatch.setattr(search_service, "search_event_media", fake_search_event_media)
    monkeypatch.setattr(
        search_service,
        "count_searchable_event_media",
        fake_count_searchable_event_media,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/events/{event_id}/search",
            headers=auth_headers(),
            params={
                "q": "stage",
                "include_duplicates": "true",
                "include_blurry": "false",
                "include_pending": "false",
                "export_ready_only": "true",
                "min_score": "0.4",
            },
        )
    finally:
        app.dependency_overrides.clear()

    expected = search_service.SearchFilters(
        include_duplicates=True,
        include_blurry=False,
        include_pending=False,
        export_ready_only=True,
        min_score=0.4,
    )
    assert response.status_code == 200
    assert captured["search"] == expected
    assert captured["count_query"] == "stage"
    assert captured["count"] == expected
