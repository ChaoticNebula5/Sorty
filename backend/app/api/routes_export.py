import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.schemas.common import APIResponse
from app.schemas.export import ExportCreateRequest, ExportJobRead
from app.services import event_service, export_service, storage_factory

router = APIRouter(
    prefix="/api",
    tags=["export"],
    dependencies=[Depends(require_api_key)],
)


def export_job_to_read(export_job) -> ExportJobRead:
    download_url = None
    if export_job.status == "completed":
        download_url = f"/api/exports/{export_job.id}/download"

    return ExportJobRead(
        id=export_job.id,
        event_id=export_job.event_id,
        status=export_job.status,
        export_type=export_job.export_type,
        included_count=export_job.included_count,
        excluded_count=export_job.excluded_count,
        include_duplicates=export_job.include_duplicates,
        include_blurry=export_job.include_blurry,
        include_pending=export_job.include_pending,
        download_url=download_url,
        error_message=export_job.error_message,
        created_at=export_job.created_at,
        completed_at=export_job.completed_at,
    )


@router.post(
    "/events/{event_id}/export",
    status_code=status.HTTP_201_CREATED,
)
def create_event_export(
    event_id: uuid.UUID,
    payload: ExportCreateRequest,
    db: Session = Depends(get_db),
) -> APIResponse:
    event = event_service.get_event(db, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "event_not_found",
                "message": "Event not found.",
                "details": {"event_id": str(event_id)},
            },
        )

    try:
        export_job = export_service.create_and_generate_export(
            db,
            event=event,
            payload=payload,
            storage=storage_factory.get_storage_service(),
        )
    except export_service.ExportBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "export_blocked",
                "message": str(exc),
                "details": {"event_id": str(event_id)},
            },
        ) from exc

    return APIResponse(data=export_job_to_read(export_job), error=None)


@router.get("/exports/{export_id}")
def get_export(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> APIResponse:
    export_job = export_service.get_export_job(db, export_id)
    if export_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "export_not_found",
                "message": "Export job not found.",
                "details": {"export_id": str(export_id)},
            },
        )

    return APIResponse(data=export_job_to_read(export_job), error=None)


@router.get("/exports/{export_id}/download")
def download_export(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    export_job = export_service.get_export_job(db, export_id)
    if export_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "export_not_found",
                "message": "Export job not found.",
                "details": {"export_id": str(export_id)},
            },
        )
    if export_job.status != "completed" or export_job.zip_object_key is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "export_not_ready",
                "message": "Export is not ready for download.",
                "details": {"export_id": str(export_id), "status": export_job.status},
            },
        )

    try:
        data = storage_factory.get_storage_service().get_bytes(export_job.zip_object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "storage_unavailable",
                "message": "Could not retrieve export from storage.",
                "details": {"export_id": str(export_id)},
            },
        ) from exc

    return StreamingResponse(
        BytesIO(data),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{export_job.id}.zip"',
        },
    )
