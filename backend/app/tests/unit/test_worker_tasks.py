import uuid
from types import SimpleNamespace

import pytest

from worker import tasks


class FakeSession:
    def __init__(self) -> None:
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def rollback(self) -> None:
        self.rolled_back = True


def test_process_batch_job_marks_job_and_media_completed(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(id=uuid.uuid4())
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_processing",
        lambda db, job: calls.append("job_processing"),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_batch_media_processing",
        lambda db, job_id: calls.append("media_processing"),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_batch_media_processed",
        lambda db, job_id: calls.append("media_processed"),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_completed",
        lambda db, job: calls.append("job_completed"),
    )

    result = tasks.process_batch_job({"job_id": str(job.id)})

    assert result == str(job.id)
    assert calls == [
        "job_processing",
        "media_processing",
        "media_processed",
        "job_completed",
    ]


def test_process_batch_job_marks_job_and_media_failed(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(id=uuid.uuid4())
    calls: list[str] = []

    def fail_media_processing(db, job_id):
        raise RuntimeError("processing failed")

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks.media_service,
        "mark_batch_media_processing",
        fail_media_processing,
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_batch_media_failed",
        lambda db, job_id, error_message: calls.append("media_failed"),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_failed",
        lambda db, job, error_message: calls.append("job_failed"),
    )

    with pytest.raises(RuntimeError):
        tasks.process_batch_job({"job_id": str(job.id)})

    assert fake_db.rolled_back is True
    assert calls == ["media_failed", "job_failed"]


def test_process_batch_job_raises_for_missing_job(monkeypatch) -> None:
    fake_db = FakeSession()
    job_id = uuid.uuid4()

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: None)

    with pytest.raises(ValueError):
        tasks.process_batch_job({"job_id": str(job_id)})
