import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.schemas.common import APIListResponse, APIResponse, Pagination
from app.schemas.media import BatchUploadRejectedItem, BatchUploadResponse, MediaAssetRead
from app.services import event_service, job_service, media_service, queue_service, storage_factory
from app.services.media_service import MediaAssetCreate
from app.services.storage_service import StorageService
from app.services.thumbnail_service import ThumbnailError, generate_thumbnail_jpeg
from app.services.upload_validation_service import (
    UploadValidationError,
    validate_upload,
)

router = APIRouter(
    prefix="/api",
    tags=["media"],
    dependencies=[Depends(require_api_key)],
)


def media_to_read(media) -> MediaAssetRead:
    item = MediaAssetRead.model_validate(media)
    item.thumbnail_url = f"/api/media/{media.id}/thumbnail"
    item.file_url = f"/api/media/{media.id}/file"
    return item


def get_media_or_404(db: Session, media_id: uuid.UUID):
    media = media_service.get_media_asset(db, media_id)
    if media is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "media_not_found",
                "message": "Media asset not found.",
                "details": {"media_id": str(media_id)},
            },
        )

    return media


def stream_storage_object(
    object_key: str,
    media_type: str,
    filename: str | None = None,
) -> StreamingResponse:
    try:
        data = storage_factory.get_storage_service().get_bytes(object_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "storage_unavailable",
                "message": "Could not retrieve media from storage.",
                "details": {},
            },
        ) from exc

    headers = {}
    if filename is not None:
        headers["Content-Disposition"] = f'inline; filename="{filename}"'

    return StreamingResponse(
        BytesIO(data),
        media_type=media_type,
        headers=headers,
    )


def cleanup_failed_upload(
    db: Session,
    storage: StorageService,
    media,
) -> None:
    for object_key in (media.original_object_key, media.thumbnail_object_key):
        if object_key is None:
            continue
        try:
            storage.delete_object(object_key)
        except Exception:
            # Cleanup is best-effort; the failed upload is still removed from DB below.
            pass

    db.delete(media)
    db.commit()


@router.post(
    "/events/{event_id}/media/batch-upload",
    status_code=status.HTTP_201_CREATED,
)
async def batch_upload_media(
    event_id: uuid.UUID,
    files: list[UploadFile] = File(...),
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

    storage = storage_factory.get_storage_service()
    accepted_media_ids: list[uuid.UUID] = []
    rejected_files: list[BatchUploadRejectedItem] = []
    job_id: uuid.UUID | None = None
    job_status: str | None = None

    for file in files:
        filename = file.filename or "unnamed"

        try:
            data = await file.read()
            validation = validate_upload(filename, file.content_type, data)
            thumbnail = generate_thumbnail_jpeg(data)

            media = media_service.create_media_asset(
                db,
                MediaAssetCreate(
                    event_id=event_id,
                    original_filename=validation.sanitized_filename,
                    mime_type=validation.mime_type,
                    file_extension=validation.file_extension,
                    size_bytes=validation.size_bytes,
                ),
            )

            try:
                storage.put_bytes(
                    media.original_object_key,
                    data,
                    validation.mime_type,
                )
                storage.put_bytes(
                    media.thumbnail_object_key,
                    thumbnail,
                    "image/jpeg",
                )
            except Exception:
                cleanup_failed_upload(db, storage, media)
                rejected_files.append(
                    BatchUploadRejectedItem(
                        filename=filename,
                        code="storage_failed",
                        message="Could not store uploaded file.",
                    )
                )
                continue

            accepted_media_ids.append(media.id)
        except UploadValidationError as exc:
            rejected_files.append(
                BatchUploadRejectedItem(
                    filename=filename,
                    code=exc.code,
                    message=exc.message,
                )
            )
        except ThumbnailError as exc:
            rejected_files.append(
                BatchUploadRejectedItem(
                    filename=filename,
                    code="thumbnail_failed",
                    message=str(exc),
                )
            )

    if accepted_media_ids:
        job = job_service.create_batch_job(
            db,
            event_id=event_id,
            total_files=len(accepted_media_ids),
        )
        media_service.attach_media_to_batch_job(db, accepted_media_ids, job.id)

        try:
            rq_job_id = queue_service.enqueue_batch_processing(
                job_id=job.id,
                event_id=event_id,
                media_ids=accepted_media_ids,
            )
        except Exception as exc:
            job_service.mark_job_failed(db, job, "Could not enqueue processing job.")
            media_service.mark_batch_media_failed(
                db,
                job.id,
                "Could not enqueue processing job.",
            )
            job_id = job.id
            job_status = "failed"
        else:
            queued_job = job_service.mark_job_queued(db, job, rq_job_id)
            job_id = queued_job.id
            job_status = queued_job.status

    response = BatchUploadResponse(
        event_id=event_id,
        job_id=job_id,
        job_status=job_status,
        accepted_count=len(accepted_media_ids),
        rejected_count=len(rejected_files),
        media_ids=accepted_media_ids,
        rejected_files=rejected_files,
    )

    return APIResponse(data=response, error=None)


@router.get("/events/{event_id}/media")
def list_event_media(
    event_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> APIListResponse:
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

    media_items = media_service.list_event_media(
        db,
        event_id=event_id,
        limit=limit,
        offset=offset,
    )
    total = media_service.count_event_media(db, event_id)

    return APIListResponse(
        data=[media_to_read(media) for media in media_items],
        pagination=Pagination(
            limit=limit,
            offset=offset,
            total=total,
        ),
        error=None,
    )


@router.get("/media/{media_id}")
def get_media(
    media_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> APIResponse:
    media = get_media_or_404(db, media_id)
    return APIResponse(data=media_to_read(media), error=None)


@router.get("/media/{media_id}/thumbnail")
def get_media_thumbnail(
    media_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    media = get_media_or_404(db, media_id)
    if media.thumbnail_object_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "thumbnail_not_found",
                "message": "Thumbnail not found.",
                "details": {"media_id": str(media_id)},
            },
        )

    return stream_storage_object(
        media.thumbnail_object_key,
        media_type="image/jpeg",
        filename=f"{media.id}-thumbnail.jpg",
    )


@router.get("/media/{media_id}/file")
def get_media_file(
    media_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    media = get_media_or_404(db, media_id)
    return stream_storage_object(
        media.original_object_key,
        media_type=media.mime_type,
        filename=media.stored_filename,
    )
