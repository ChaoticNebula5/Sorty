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
