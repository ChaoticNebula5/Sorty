import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.schemas.common import APIResponse
from app.schemas.jobs import BatchJobRead
from app.services import job_service

router = APIRouter(
    prefix="/api/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_api_key)],
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
