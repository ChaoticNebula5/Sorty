from types import SimpleNamespace
import uuid

from sqlalchemy.dialects import postgresql

from app.db.models import BatchJob
from app.services import job_service


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = False

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item: object) -> None:
        self.refreshed = True


def test_mark_job_failed_updates_failed_file_count() -> None:
    db = FakeDb()
    job = SimpleNamespace(
        status="processing",
        total_files=4,
        failed_files=0,
        error_message=None,
        completed_at=None,
    )

    result = job_service.mark_job_failed(db, job, "boom")

    assert result is job
    assert job.status == "failed"
    assert job.failed_files == 4
    assert job.error_message == "boom"
    assert job.completed_at is not None
    assert db.committed is True
    assert db.refreshed is True



def test_mark_job_finished_prioritizes_review_before_partial_failure() -> None:
    db = FakeDb()
    job = SimpleNamespace(
        status="processing",
        processed_files=0,
        failed_files=0,
        needs_review_count=0,
        error_message=None,
        completed_at=None,
    )

    result = job_service.mark_job_finished(
        db,
        job,
        processed_files=2,
        failed_files=1,
        needs_review_count=1,
    )

    assert result is job
    assert job.status == "waiting_for_review"
    assert job.processed_files == 2
    assert job.failed_files == 1
    assert job.needs_review_count == 1
    assert job.error_message == "One or more media assets failed processing."
    assert job.completed_at is not None
    assert db.committed is True
    assert db.refreshed is True


def test_mark_job_finished_uses_partial_failure_when_no_review_needed() -> None:
    db = FakeDb()
    job = SimpleNamespace(
        status="processing",
        processed_files=0,
        failed_files=0,
        needs_review_count=0,
        error_message=None,
        completed_at=None,
    )

    result = job_service.mark_job_finished(
        db,
        job,
        processed_files=2,
        failed_files=1,
        needs_review_count=0,
    )

    assert result is job
    assert job.status == "partial_failed"
    assert job.error_message == "One or more media assets failed processing."
    assert db.committed is True
    assert db.refreshed is True


def test_mark_job_resume_completed_updates_completion_fields() -> None:
    db = FakeDb()
    job = SimpleNamespace(
        status="processing",
        total_files=5,
        processed_files=2,
        failed_files=1,
        needs_review_count=2,
        current_rq_job_id="resume-job",
        error_message="placeholder",
        completed_at=None,
    )

    result = job_service.mark_job_resume_completed(db, job)

    assert result is job
    assert job.status == "completed"
    assert job.current_rq_job_id is None
    assert job.error_message is None
    assert job.needs_review_count == 0
    assert job.processed_files == 4
    assert job.completed_at is not None
    assert db.committed is True
    assert db.refreshed is True


def test_list_event_jobs_uses_deterministic_ordering() -> None:
    captured = {}

    class FakeDb:
        def scalars(self, statement):
            captured["statement"] = statement
            return []

    event_id = uuid.uuid4()

    result = job_service.list_event_jobs(FakeDb(), event_id, limit=10, offset=20)

    compiled = str(
        captured["statement"].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert result == []
    assert "ORDER BY batch_jobs.created_at DESC, batch_jobs.id DESC" in compiled
    assert "LIMIT 10" in compiled
    assert "OFFSET 20" in compiled
    assert BatchJob.__tablename__ in compiled
