from types import SimpleNamespace

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
