import uuid
from typing import Any

import redis
from rq import Queue

from app.core.config import get_settings
from worker.tasks import process_batch_job


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
