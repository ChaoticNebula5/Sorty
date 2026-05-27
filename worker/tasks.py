import uuid
from typing import Any

from app.db.session import SessionLocal
from app.services import job_service, media_service


def health_check_task() -> str:
    return "ok"


def process_batch_job(payload: dict[str, Any]) -> str:
    job_id = uuid.UUID(str(payload["job_id"]))

    with SessionLocal() as db:
        job = job_service.get_batch_job(db, job_id)
        if job is None:
            raise ValueError(f"Batch job not found: {job_id}")

        try:
            job_service.mark_job_processing(db, job)
            media_service.mark_batch_media_processing(db, job.id)
            media_service.mark_batch_media_processed(db, job.id)
            job_service.mark_job_completed(db, job)
        except Exception as exc:
            db.rollback()
            media_service.mark_batch_media_failed(db, job.id, str(exc))
            job_service.mark_job_failed(db, job, str(exc))
            raise

    return str(job_id)
