"""Opt-in PostgreSQL/MinIO test with fault-injected Gemini; no external AI calls."""
from io import BytesIO
import json
import os
import random
from types import SimpleNamespace
import uuid

from fastapi.testclient import TestClient
from google.genai.errors import APIError
from PIL import Image
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import AIAnalysis, MediaAsset
from app.db.session import SessionLocal
from app.main import app
from app.services import job_service, queue_service, vision_service
from worker.tasks import process_batch_job, resume_batch_job

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv("SORTY_RETRY_INTEGRATION") != "1", reason="Set SORTY_RETRY_INTEGRATION=1 with local PostgreSQL/MinIO running.",
)]


@pytest.mark.parametrize("review_first", [False, True])
def test_eight_images_daily_quota_then_retry_only_remaining_five(monkeypatch, review_first):
    class FakeModels:
        calls = 0
        quota_exhausted = True

        def generate_content(self, **kwargs):
            self.calls += 1
            if self.quota_exhausted and self.calls > 3:
                raise APIError(429, {"error": {"details": [{
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
                }]}})
            result = vision_service.MockVisionProvider().analyze_image("sample", {"event_type": "test"})
            if review_first and self.calls == 1:
                result.needs_review = True
                result.review_reasons = ["uncertain_subject"]
            return SimpleNamespace(text=json.dumps(result.model_dump()))

    models = FakeModels()

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = models
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(vision_service, "_load_gemini_sdk", lambda: SimpleNamespace(Client=FakeClient))
    provider = vision_service.GeminiVisionProvider(api_key="local-fault-injection-only", model_name="fault-test")
    monkeypatch.setattr(vision_service, "get_vision_provider", lambda: provider)
    enqueued = []
    def fake_enqueue(**kwargs):
        enqueued.append(kwargs)
        return kwargs.get("rq_job_id") or f"test-{uuid.uuid4()}"
    monkeypatch.setattr(queue_service, "enqueue_batch_processing", fake_enqueue)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {get_settings().admin_token}"
        response = client.post("/api/events", json={"name": f"Backoff recovery test {uuid.uuid4().hex[:8]}"})
        assert response.status_code == 201
        event_id = response.json()["data"]["id"]
        files = []
        for i in range(8):
            data = bytes(random.Random(i).randbytes(128 * 128 * 3))
            image = Image.frombytes("RGB", (128, 128), data)
            stream = BytesIO()
            image.save(stream, format="PNG")
            files.append(("files", (f"photo-{i}.png", stream.getvalue(), "image/png")))
        response = client.post(f"/api/events/{event_id}/media/batch-upload", files=files)
        assert response.status_code == 201
        upload = response.json()["data"]
        assert upload["accepted_count"] == 8
        job_id = uuid.UUID(upload["job_id"])
        media_ids = [uuid.UUID(value) for value in upload["media_ids"]]
        process_batch_job({"job_id": str(job_id)})
        with SessionLocal() as db:
            job = job_service.get_batch_job(db, job_id)
            assert (job.processed_files, job.failed_files, job.needs_review_count) == (3 - int(review_first), 5, int(review_first))
            assert job.status == ("waiting_for_review" if review_first else "partial_failed")
            assert "quota" in job.error_message.lower()
            original_analyses = {row.media_id: row.id for row in db.scalars(select(AIAnalysis).where(AIAnalysis.media_id.in_(media_ids)))}
            assert set(original_analyses) == set(media_ids[:3])
        assert models.calls == 4  # no requests for the remaining four after daily quota

        models.quota_exhausted = False
        response = client.post(f"/api/jobs/{job_id}/retry")
        assert response.status_code == 200, response.text
        assert enqueued[-1]["media_ids"] == media_ids[3:]
        assert client.post(f"/api/jobs/{job_id}/retry").status_code == 409
        process_batch_job({"job_id": str(job_id)})
        with SessionLocal() as db:
            job = job_service.get_batch_job(db, job_id)
            assert (job.processed_files, job.failed_files, job.needs_review_count) == (8 - int(review_first), 0, int(review_first))
            assert job.status == ("waiting_for_review" if review_first else "completed")
            analyses = {row.media_id: row.id for row in db.scalars(select(AIAnalysis).where(AIAnalysis.media_id.in_(media_ids)))}
            assert len(analyses) == 8
            assert all(analyses[key] == value for key, value in original_analyses.items())
            assert len(list(db.scalars(select(MediaAsset).where(MediaAsset.event_id == uuid.UUID(event_id))))) == 8
        assert models.calls == 9  # 3 initial successes + 1 quota error + 5 retry successes
        if review_first:
            assert client.post(f"/api/jobs/{job_id}/resume").status_code == 409
            response = client.patch(f"/api/media/{media_ids[0]}/review", json={
                "status": "approved", "final_primary_folder": "Highlights", "include_in_export": True,
            })
            assert response.status_code == 200
            monkeypatch.setattr(queue_service, "enqueue_batch_resume", lambda **kwargs: f"resume-{job_id}-batch-{job_id}")
            assert client.post(f"/api/jobs/{job_id}/resume").status_code == 200
            resume_batch_job({"job_id": str(job_id), "event_id": event_id, "thread_id": f"batch-{job_id}", "mode": "resume"})
            with SessionLocal() as db:
                assert job_service.get_batch_job(db, job_id).status == "completed"
            assert models.calls == 9
