import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
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


def claim_job_for_resume(db: Session, job: BatchJob) -> BatchJob:
    if job.status != "reviewed":
        raise ValueError("Only reviewed jobs can be claimed for resume.")

    job.status = "queued"
    job.current_rq_job_id = "resume-pending"
    job.error_message = None
    db.commit()
    db.refresh(job)
    return job


def mark_job_resume_enqueue_failed(db: Session, job: BatchJob) -> BatchJob:
    job.status = "reviewed"
    job.current_rq_job_id = None
    job.error_message = "Could not enqueue resume job."
    db.commit()
    db.refresh(job)
    return job


def mark_job_review_resume_queued(
    db: Session,
    job: BatchJob,
    rq_job_id: str,
) -> BatchJob:
    job.current_rq_job_id = rq_job_id
    job.error_message = None
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


def mark_job_partial_failed(
    db: Session,
    job: BatchJob,
    processed_files: int,
    failed_files: int,
    error_message: str,
) -> BatchJob:
    job.status = "partial_failed"
    job.processed_files = processed_files
    job.failed_files = failed_files
    job.error_message = error_message
    job.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def mark_job_finished(
    db: Session,
    job: BatchJob,
    processed_files: int,
    failed_files: int,
    needs_review_count: int,
) -> BatchJob:
    job.processed_files = processed_files
    job.failed_files = failed_files
    job.needs_review_count = needs_review_count
    job.completed_at = datetime.now(UTC)

    if failed_files:
        job.status = "partial_failed"
        job.error_message = "One or more media assets failed processing."
    elif needs_review_count:
        job.status = "waiting_for_review"
        job.error_message = None
    else:
        job.status = "completed"
        job.error_message = None

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


def mark_job_reviewed_if_complete(db: Session, job: BatchJob) -> BatchJob:
    job.status = "reviewed"
    job.needs_review_count = 0
    db.commit()
    db.refresh(job)
    return job


def get_batch_job(db: Session, job_id: uuid.UUID) -> BatchJob | None:
    return db.scalar(select(BatchJob).where(BatchJob.id == job_id))


def list_event_jobs(
    db: Session,
    event_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[BatchJob]:
    return list(
        db.scalars(
            select(BatchJob)
            .where(BatchJob.event_id == event_id)
            .order_by(BatchJob.created_at.desc(), BatchJob.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def count_event_jobs(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(BatchJob).where(BatchJob.event_id == event_id)
    ) or 0
