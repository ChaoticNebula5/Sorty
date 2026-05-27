import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_jobs import job_service
from app.core.config import get_settings
from app.main import app


def override_db() -> Generator[object, None, None]:
    yield object()


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().app_api_key}


def make_job(**overrides: object) -> SimpleNamespace:
    job_id = uuid.uuid4()
    event_id = uuid.uuid4()
    now = datetime.now(UTC)
    data = {
        "id": job_id,
        "event_id": event_id,
        "current_rq_job_id": "rq-job-id",
        "status": "queued",
        "total_files": 3,
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


def test_get_job_requires_api_key() -> None:
    response = TestClient(app).get(f"/api/jobs/{uuid.uuid4()}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_get_job_returns_job(monkeypatch) -> None:
    job = make_job()

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/jobs/{job.id}",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == str(job.id)
    assert body["data"]["status"] == "queued"
    assert body["data"]["total_files"] == 3


def test_get_job_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).get(
            f"/api/jobs/{uuid.uuid4()}",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"
