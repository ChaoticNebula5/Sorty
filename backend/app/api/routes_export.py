import base64
import hashlib
import hmac
import json
import time
import uuid
from io import BytesIO
from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin_auth
from app.core.config import get_settings
from app.schemas.common import APIResponse
from app.schemas.export import ExportCreateRequest, ExportJobRead
from app.services import event_service, export_service, queue_service, storage_factory

download_bearer_token = HTTPBearer(auto_error=False)
EXPORT_DOWNLOAD_TOKEN_TTL_SECONDS = 600

router = APIRouter(
    prefix="/api",
    tags=["export"],
)


def export_job_to_read(export_job) -> ExportJobRead:
    download_url = None
    if export_job.status == "completed":
        token = create_export_download_token(export_job.id)
        download_url = f"/api/exports/{export_job.id}/download?token={token}"

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


def create_export_download_token(export_id: uuid.UUID) -> str:
    settings = get_settings()
    payload = {
        "export_id": str(export_id),
        "exp": int(time.time()) + EXPORT_DOWNLOAD_TOKEN_TTL_SECONDS,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    payload_part = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
    signature = hmac.new(
        settings.admin_token.encode(),
        payload_part.encode(),
        hashlib.sha256,
    ).digest()
    signature_part = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{payload_part}.{signature_part}"


def validate_export_download_token(token: str, export_id: uuid.UUID) -> bool:
    settings = get_settings()
    try:
        payload_part, signature_part = token.split(".", maxsplit=1)
        expected_signature = hmac.new(
            settings.admin_token.encode(),
            payload_part.encode(),
            hashlib.sha256,
        ).digest()
        expected_signature_part = (
            base64.urlsafe_b64encode(expected_signature).decode().rstrip("=")
        )
        if not compare_digest(signature_part, expected_signature_part):
            return False

        padded_payload = payload_part + ("=" * (-len(payload_part) % 4))
        payload = json.loads(base64.urlsafe_b64decode(padded_payload.encode()))
    except Exception:
        return False

    return (
        payload.get("export_id") == str(export_id)
        and int(payload.get("exp", 0)) >= int(time.time())
    )


def require_export_download_auth(
    export_id: uuid.UUID,
    download_token: str | None = Query(default=None, alias="token"),
    credentials: HTTPAuthorizationCredentials | None = Security(download_bearer_token),
) -> None:
    settings = get_settings()
    if credentials is not None:
        if (
            credentials.scheme.lower() == "bearer"
            and compare_digest(credentials.credentials, settings.admin_token)
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_admin_token",
                "message": "Invalid admin token.",
            },
        )

    if download_token and validate_export_download_token(download_token, export_id):
        return
    if download_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_admin_token",
                "message": "Invalid admin token.",
            },
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "missing_admin_token",
            "message": "Missing Authorization bearer token.",
        },
    )


@router.post(
    "/events/{event_id}/export",
    status_code=status.HTTP_201_CREATED,
)
def create_event_export(
    event_id: uuid.UUID,
    payload: ExportCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_auth),
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
        export_job = export_service.create_export_job(
            db,
            event=event,
            payload=payload,
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

    queued_export_job = export_service.mark_export_queued(db, export_job)

    try:
        queue_service.enqueue_export(queued_export_job.id)
    except Exception as exc:
        export_service.mark_export_failed(
            db,
            queued_export_job,
            "Could not enqueue export job.",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "queue_unavailable",
                "message": "Could not enqueue export job.",
                "details": {"export_id": str(queued_export_job.id)},
            },
        ) from exc

    return APIResponse(data=export_job_to_read(queued_export_job), error=None)


@router.get("/exports/{export_id}")
def get_export(
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_auth),
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
    _: None = Depends(require_export_download_auth),
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
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
