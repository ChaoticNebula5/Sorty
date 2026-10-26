import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin_auth
from app.schemas.common import APIResponse
from app.schemas.jobs import BatchJobRead, JobResumeResponse
from app.services import job_service, media_service, queue_service, review_service

router = APIRouter(
    prefix="/api/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_admin_auth)],
)


@router.get("/{job_id}")
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> APIResponse:
    job = job_service.get_batch_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "job_not_found",
                "message": "Job not found.",
                "details": {"job_id": str(job_id)},
            },
        )

    return APIResponse(data=BatchJobRead.model_validate(job), error=None)


@router.post("/{job_id}/resume")
def resume_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> APIResponse:
    job = job_service.get_batch_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "job_not_found",
                "message": "Job not found.",
                "details": {"job_id": str(job_id)},
            },
        )

    resume_rq_job_id = queue_service.build_resume_rq_job_id(
        job_id=job.id,
        thread_id=job.langgraph_thread_id,
    )
    is_claimed_resume = (
        job.status == "queued" and job.current_rq_job_id == resume_rq_job_id
    )

    if job.status not in {"waiting_for_review", "reviewed"} and not is_claimed_resume:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_job_status",
                "message": "Only reviewed or already claimed resume jobs can be resumed.",
                "details": {"job_id": str(job_id), "status": job.status},
            },
        )

    if job.failed_files:
        raise HTTPException(409, detail={
            "code": "processing_incomplete",
            "message": "Retry failed images before resuming the review workflow.",
        })

    pending_count = review_service.count_pending_reviews_for_batch(db, job.id)
    if pending_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "unresolved_review_items",
                "message": "Resolve all pending review items before resuming.",
                "details": {"job_id": str(job_id), "pending_count": pending_count},
            },
        )

    invalid_count = review_service.count_invalid_resolved_reviews_for_batch(db, job.id)
    if invalid_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_review_decisions",
                "message": "Fix invalid review decisions before resuming.",
                "details": {"job_id": str(job_id), "invalid_count": invalid_count},
            },
        )

    if job.status == "waiting_for_review":
        job = job_service.mark_job_reviewed_if_complete(db, job)

    if is_claimed_resume:
        claimed_job = job
    else:
        try:
            claimed_job = job_service.claim_job_for_resume(db, job.id, resume_rq_job_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "invalid_job_status",
                    "message": str(exc),
                    "details": {"job_id": str(job_id), "status": job.status},
                },
            ) from exc

    try:
        rq_job_id = queue_service.enqueue_batch_resume(
            job_id=claimed_job.id,
            event_id=claimed_job.event_id,
            thread_id=claimed_job.langgraph_thread_id,
        )
    except Exception as exc:
        job_service.mark_job_resume_enqueue_failed(db, claimed_job)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "queue_unavailable",
                "message": "Could not enqueue resume job.",
                "details": {
                    "job_id": str(job_id),
                    "rq_job_id": resume_rq_job_id,
                    "retryable": True,
                },
            },
        ) from exc

    return APIResponse(
        data=JobResumeResponse(
            job_id=claimed_job.id,
            status=claimed_job.status,
            rq_job_id=rq_job_id,
            thread_id=claimed_job.langgraph_thread_id,
            message="Resume job queued.",
        ),
        error=None,
    )


@router.post("/{job_id}/retry")
def retry_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> APIResponse:
    job = job_service.get_batch_job(db, job_id)
    if job is None:
        raise HTTPException(404, detail={"code": "job_not_found", "message": "Job not found."})
    if job.status in {"queued", "processing", "created", "exporting"}:
        raise HTTPException(409, detail={"code": "invalid_job_status", "message": "Wait for this batch to stop before retrying."})
    candidates = [m for m in media_service.list_batch_media(db, job.id) if media_service.should_retry_media(m)]
    if not candidates:
        raise HTTPException(409, detail={"code": "no_retryable_media", "message": "No failed or unfinished images to retry."})
    previous_status = job.status
    rq_job_id = f"retry-{job.id}-{uuid.uuid4()}"
    try:
        claimed = job_service.claim_job_for_retry(db, job.id, rq_job_id)
    except ValueError as exc:
        raise HTTPException(409, detail={"code": "invalid_job_status", "message": str(exc)}) from exc
    try:
        queue_service.enqueue_batch_processing(
            job_id=claimed.id, event_id=claimed.event_id,
            media_ids=[m.id for m in candidates], rq_job_id=rq_job_id,
        )
    except Exception as exc:
        job_service.mark_job_retry_enqueue_failed(db, claimed, previous_status)
        raise HTTPException(503, detail={"code": "queue_unavailable", "message": "Could not enqueue retry. Please try again."}) from exc
    return APIResponse(data=JobResumeResponse(
        job_id=claimed.id, status="queued", rq_job_id=rq_job_id,
        thread_id=claimed.langgraph_thread_id, message="Retrying failed and unfinished images; successful images are preserved.",
    ), error=None)
