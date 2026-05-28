import uuid
from typing import Any

import redis
from rq import Queue

from app.core.config import get_settings
from worker.tasks import generate_export_job, process_batch_job, resume_batch_job


def build_resume_rq_job_id(job_id: uuid.UUID, thread_id: str) -> str:
    return f"resume:{job_id}:{thread_id}"


def _get_rq_job_status(job: object) -> str | None:
    get_status = getattr(job, "get_status", None)
    if callable(get_status):
        status = get_status(refresh=False)
    else:
        status = getattr(job, "status", None)

    if status is None:
        return None

    value = getattr(status, "value", None)
    if value is not None:
        return str(value)

    return str(status)


def _is_reusable_resume_job(job: object) -> bool:
    return _get_rq_job_status(job) in {"queued", "started", "deferred", "scheduled"}


def _delete_rq_job_if_possible(job: object) -> None:
    delete = getattr(job, "delete", None)
    if callable(delete):
        delete()


def enqueue_batch_processing(
    job_id: uuid.UUID,
    event_id: uuid.UUID,
    media_ids: list[uuid.UUID],
) -> str:
    settings = get_settings()
    connection = redis.from_url(settings.redis_url)
    queue = Queue(settings.rq_queue_name, connection=connection)
    payload: dict[str, Any] = {
        "job_id": str(job_id),
        "event_id": str(event_id),
        "media_ids": [str(media_id) for media_id in media_ids],
        "mode": "start",
    }
    rq_job = queue.enqueue(process_batch_job, payload)
    return rq_job.id


def enqueue_batch_resume(
    job_id: uuid.UUID,
    event_id: uuid.UUID,
    thread_id: str,
) -> str:
    settings = get_settings()
    connection = redis.from_url(settings.redis_url)
    queue = Queue(settings.rq_queue_name, connection=connection)
    payload: dict[str, Any] = {
        "job_id": str(job_id),
        "event_id": str(event_id),
        "thread_id": thread_id,
        "mode": "resume",
    }
    rq_job_id = build_resume_rq_job_id(job_id, thread_id)
    existing_job = queue.fetch_job(rq_job_id)
    if existing_job is not None and _is_reusable_resume_job(existing_job):
        return rq_job_id
    if existing_job is not None:
        _delete_rq_job_if_possible(existing_job)

    try:
        rq_job = queue.enqueue(
            resume_batch_job,
            payload,
            job_id=rq_job_id,
        )
    except Exception:
        existing_job = queue.fetch_job(rq_job_id)
        if existing_job is not None and _is_reusable_resume_job(existing_job):
            return rq_job_id
        raise

    return rq_job.id


def enqueue_export(export_id: uuid.UUID) -> str:
    settings = get_settings()
    connection = redis.from_url(settings.redis_url)
    queue = Queue(settings.rq_queue_name, connection=connection)
    payload: dict[str, Any] = {
        "export_id": str(export_id),
        "mode": "export",
    }
    rq_job = queue.enqueue(generate_export_job, payload)
    return rq_job.id
