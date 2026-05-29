import uuid
from types import SimpleNamespace

from rq.job import JobStatus

from app.services import queue_service


class FakeQueue:
    def __init__(self, name: str, connection: object) -> None:
        self.name = name
        self.connection = connection
        self.existing_job = None

    def fetch_job(self, job_id: str):
        return self.existing_job

    def enqueue(self, func, payload, job_id=None):
        self.func = func
        self.payload = payload
        self.job_id = job_id
        return SimpleNamespace(id=job_id or "generated-job-id")


class FakeJob:
    def __init__(self, status: str) -> None:
        self.status = status
        self.deleted = False

    def get_status(self, refresh: bool = True) -> str:
        return self.status

    def delete(self) -> None:
        self.deleted = True


def test_enqueue_batch_resume_uses_deterministic_job_id(monkeypatch) -> None:
    captured = {}

    def fake_queue(name: str, connection: object):
        queue = FakeQueue(name, connection)
        captured["queue"] = queue
        return queue

    job_id = uuid.uuid4()
    event_id = uuid.uuid4()
    thread_id = f"batch-{job_id}"

    monkeypatch.setattr(queue_service.redis, "from_url", lambda url: object())
    monkeypatch.setattr(queue_service, "Queue", fake_queue)

    rq_job_id = queue_service.enqueue_batch_resume(
        job_id=job_id,
        event_id=event_id,
        thread_id=thread_id,
    )

    assert rq_job_id == f"resume-{job_id}-{thread_id}"
    assert captured["queue"].job_id == f"resume-{job_id}-{thread_id}"
    assert captured["queue"].payload == {
        "job_id": str(job_id),
        "event_id": str(event_id),
        "thread_id": thread_id,
        "mode": "resume",
    }


def test_enqueue_batch_resume_returns_existing_deterministic_job(monkeypatch) -> None:
    captured = {}

    def fake_queue(name: str, connection: object):
        queue = FakeQueue(name, connection)
        queue.existing_job = FakeJob(status="queued")
        captured["queue"] = queue
        return queue

    job_id = uuid.uuid4()
    thread_id = f"batch-{job_id}"

    monkeypatch.setattr(queue_service.redis, "from_url", lambda url: object())
    monkeypatch.setattr(queue_service, "Queue", fake_queue)

    rq_job_id = queue_service.enqueue_batch_resume(
        job_id=job_id,
        event_id=uuid.uuid4(),
        thread_id=thread_id,
    )

    assert rq_job_id == f"resume-{job_id}-{thread_id}"
    assert not hasattr(captured["queue"], "payload")


def test_enqueue_batch_resume_treats_rq_status_enum_as_reusable(monkeypatch) -> None:
    captured = {}

    def fake_queue(name: str, connection: object):
        queue = FakeQueue(name, connection)
        queue.existing_job = FakeJob(status=JobStatus.QUEUED)
        captured["queue"] = queue
        return queue

    job_id = uuid.uuid4()
    thread_id = f"batch-{job_id}"

    monkeypatch.setattr(queue_service.redis, "from_url", lambda url: object())
    monkeypatch.setattr(queue_service, "Queue", fake_queue)

    rq_job_id = queue_service.enqueue_batch_resume(
        job_id=job_id,
        event_id=uuid.uuid4(),
        thread_id=thread_id,
    )

    assert rq_job_id == f"resume-{job_id}-{thread_id}"
    assert not hasattr(captured["queue"], "payload")


def test_enqueue_batch_resume_replaces_terminal_existing_job(monkeypatch) -> None:
    captured = {}
    terminal_job = FakeJob(status="finished")

    def fake_queue(name: str, connection: object):
        queue = FakeQueue(name, connection)
        queue.existing_job = terminal_job
        captured["queue"] = queue
        return queue

    job_id = uuid.uuid4()
    event_id = uuid.uuid4()
    thread_id = f"batch-{job_id}"

    monkeypatch.setattr(queue_service.redis, "from_url", lambda url: object())
    monkeypatch.setattr(queue_service, "Queue", fake_queue)

    rq_job_id = queue_service.enqueue_batch_resume(
        job_id=job_id,
        event_id=event_id,
        thread_id=thread_id,
    )

    assert rq_job_id == f"resume-{job_id}-{thread_id}"
    assert terminal_job.deleted is True
    assert captured["queue"].job_id == f"resume-{job_id}-{thread_id}"


def test_enqueue_export_sends_export_payload(monkeypatch) -> None:
    captured = {}

    def fake_queue(name: str, connection: object):
        queue = FakeQueue(name, connection)
        captured["queue"] = queue
        return queue

    export_id = uuid.uuid4()

    monkeypatch.setattr(queue_service.redis, "from_url", lambda url: object())
    monkeypatch.setattr(queue_service, "Queue", fake_queue)

    rq_job_id = queue_service.enqueue_export(export_id)

    assert rq_job_id == "generated-job-id"
    assert captured["queue"].payload == {
        "export_id": str(export_id),
        "mode": "export",
    }
