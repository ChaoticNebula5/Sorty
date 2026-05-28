from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from app.api.routes_events import router as events_router
from app.api.routes_health import router as health_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_media import router as media_router
from app.api.routes_review import router as review_router
from app.core.config import get_settings
from app.core.errors import http_exception_handler, validation_exception_handler
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(health_router)
    app.include_router(events_router)
    app.include_router(jobs_router)
    app.include_router(media_router)
    app.include_router(review_router)

    return app


app = create_app()
