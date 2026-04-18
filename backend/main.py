"""
FastAPI application entrypoint for Sorty backend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
