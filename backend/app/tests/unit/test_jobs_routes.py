import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.routes_jobs import job_service, queue_service, review_service
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
        "langgraph_thread_id": f"batch-{job_id}",
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


def test_resume_job_requires_api_key() -> None:
    response = TestClient(app).post(f"/api/jobs/{uuid.uuid4()}/resume")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "missing_api_key"


def test_resume_job_returns_404(monkeypatch) -> None:
    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: None)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{uuid.uuid4()}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


def test_resume_job_rejects_invalid_status(monkeypatch) -> None:
    job = make_job(status="processing")

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{job.id}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_job_status"


def test_resume_job_blocks_unresolved_reviews(monkeypatch) -> None:
    job = make_job(status="waiting_for_review")

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        review_service,
        "count_pending_reviews_for_batch",
        lambda db, batch_job_id: 2,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{job.id}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "unresolved_review_items"
    assert body["error"]["details"]["pending_count"] == 2


def test_resume_job_blocks_invalid_resolved_reviews(monkeypatch) -> None:
    job = make_job(status="reviewed")

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        review_service,
        "count_pending_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(
        review_service,
        "count_invalid_resolved_reviews_for_batch",
        lambda db, batch_job_id: 1,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{job.id}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_review_decisions"


def test_resume_job_enqueues_resume(monkeypatch) -> None:
    job = make_job(status="waiting_for_review")
    enqueued_payload = {}

    def fake_enqueue_batch_resume(job_id, event_id, thread_id):
        enqueued_payload.update(
            {
                "job_id": job_id,
                "event_id": event_id,
                "thread_id": thread_id,
            }
        )
        return "resume-rq-job-id"

    def fake_mark_reviewed(db, job):
        job.status = "reviewed"
        return job

    def fake_claim_job_for_resume(db, job_id, rq_job_id):
        job.status = "queued"
        job.current_rq_job_id = rq_job_id
        return job

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        review_service,
        "count_pending_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(
        review_service,
        "count_invalid_resolved_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(job_service, "mark_job_reviewed_if_complete", fake_mark_reviewed)
    monkeypatch.setattr(job_service, "claim_job_for_resume", fake_claim_job_for_resume)
    monkeypatch.setattr(queue_service, "enqueue_batch_resume", fake_enqueue_batch_resume)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{job.id}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["job_id"] == str(job.id)
    assert body["data"]["status"] == "queued"
    assert body["data"]["rq_job_id"] == "resume-rq-job-id"
    assert body["data"]["thread_id"] == job.langgraph_thread_id
    assert body["data"]["message"] == "Resume job queued."
    assert enqueued_payload == {
        "job_id": job.id,
        "event_id": job.event_id,
        "thread_id": job.langgraph_thread_id,
    }


def test_resume_job_handles_failed_claim(monkeypatch) -> None:
    job = make_job(status="reviewed")

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        review_service,
        "count_pending_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(
        review_service,
        "count_invalid_resolved_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(
        job_service,
        "claim_job_for_resume",
        lambda db, job_id, rq_job_id: (_ for _ in ()).throw(ValueError("already claimed")),
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{job.id}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_job_status"


def test_resume_job_rejects_duplicate_queued_resume(monkeypatch) -> None:
    job = make_job(status="queued", current_rq_job_id="resume-rq-job-id")

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{job.id}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_job_status"


def test_resume_job_marks_failed_when_queue_unavailable(monkeypatch) -> None:
    job = make_job(status="reviewed")

    def fake_enqueue_batch_resume(job_id, event_id, thread_id):
        raise RuntimeError("redis down")

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        review_service,
        "count_pending_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(
        review_service,
        "count_invalid_resolved_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(queue_service, "enqueue_batch_resume", fake_enqueue_batch_resume)
    monkeypatch.setattr(job_service, "claim_job_for_resume", lambda db, job_id, rq_job_id: job)
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{job.id}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "queue_unavailable"
    assert body["error"]["details"]["retryable"] is True
    assert body["error"]["details"]["rq_job_id"] == (
        f"resume:{job.id}:{job.langgraph_thread_id}"
    )


def test_resume_job_retries_already_claimed_resume(monkeypatch) -> None:
    job = make_job(status="queued")
    job.current_rq_job_id = f"resume:{job.id}:{job.langgraph_thread_id}"
    enqueued = []

    monkeypatch.setattr(job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        review_service,
        "count_pending_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(
        review_service,
        "count_invalid_resolved_reviews_for_batch",
        lambda db, batch_job_id: 0,
    )
    monkeypatch.setattr(
        queue_service,
        "enqueue_batch_resume",
        lambda job_id, event_id, thread_id: enqueued.append(job_id)
        or job.current_rq_job_id,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        response = TestClient(app).post(
            f"/api/jobs/{job.id}/resume",
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"]["rq_job_id"] == job.current_rq_job_id
    assert enqueued == [job.id]
