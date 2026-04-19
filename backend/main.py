"""
FastAPI application entrypoint for Sorty backend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database import close_db
from backend.redis_client import close_redis
from backend.routers import (
    assets,
    assistant,
    collections,
    events,
    export,
    search,
    upload,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown resources."""
    yield
    await close_redis()
    await close_db()


app = FastAPI(
    title="Sorty Backend",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")


def _error_response(status_code: int, code: str, message, details=None) -> JSONResponse:
    """Return normalized API error envelope."""
    payload = {
        "data": None,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalize FastAPI HTTP exceptions to the project response envelope."""
    detail = exc.detail
    if isinstance(detail, dict):
        return _error_response(
            exc.status_code,
            detail.get("code", "HTTP_ERROR"),
            detail.get("message", "Request failed"),
            detail.get("details"),
        )
    return _error_response(exc.status_code, "HTTP_ERROR", str(detail))


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Normalize validation errors to the project response envelope."""
    return _error_response(
        422,
        "VALIDATION_ERROR",
        "Request validation failed",
        exc.errors(),
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
