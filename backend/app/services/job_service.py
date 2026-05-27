import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BatchJob


def create_batch_job(
    db: Session,
    event_id: uuid.UUID,
    total_files: int,
) -> BatchJob:
    job_id = uuid.uuid4()
    job = BatchJob(
        id=job_id,
        event_id=event_id,
        langgraph_thread_id=f"batch-{job_id}",
        status="created",
        total_files=total_files,
        processed_files=0,
        failed_files=0,
        needs_review_count=0,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def mark_job_queued(db: Session, job: BatchJob, rq_job_id: str) -> BatchJob:
    job.status = "queued"
    job.current_rq_job_id = rq_job_id
    db.commit()
    db.refresh(job)
    return job


def mark_job_processing(db: Session, job: BatchJob) -> BatchJob:
    job.status = "processing"
    job.started_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def mark_job_completed(db: Session, job: BatchJob) -> BatchJob:
    job.status = "completed"
    job.processed_files = job.total_files
    job.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def mark_job_failed(db: Session, job: BatchJob, error_message: str) -> BatchJob:
    job.status = "failed"
    job.failed_files = job.total_files
    job.error_message = error_message
    job.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def get_batch_job(db: Session, job_id: uuid.UUID) -> BatchJob | None:
    return db.scalar(select(BatchJob).where(BatchJob.id == job_id))


def list_event_jobs(db: Session, event_id: uuid.UUID) -> list[BatchJob]:
    return list(
        db.scalars(
            select(BatchJob)
            .where(BatchJob.event_id == event_id)
            .order_by(BatchJob.created_at.desc())
        )
    )
