from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.services import readiness_service

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "data": {
            "status": "ok",
            "app": settings.app_name,
        },
        "error": None,
    }


@router.get("/ready")
def readiness_check() -> JSONResponse:
    report = readiness_service.check_readiness()
    response_status = (
        status.HTTP_200_OK
        if report.status == "ready"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=response_status,
        content={
            "data": {
                "status": report.status,
                "components": [
                    {
                        "name": component.name,
                        "status": component.status,
                        "detail": component.detail,
                    }
                    for component in report.components
                ],
            },
            "error": None,
        },
    )
