from fastapi import APIRouter

from app.core.constants import API_PREFIX, HEALTH_PATH
from app.core.config import get_settings

router = APIRouter(prefix=API_PREFIX, tags=["health"])


@router.get(HEALTH_PATH)
def health_check() -> dict:
    settings = get_settings()
    return {
        "data": {
            "status": "ok",
            "app": settings.app_name,
        },
        "error": None,
    }
