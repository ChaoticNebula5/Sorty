"""API router package."""

from backend.routers import (
    assets,
    assistant,
    collections,
    events,
    export,
    overrides,
    search,
    upload,
)

__all__ = [
    "assets",
    "assistant",
    "collections",
    "events",
    "export",
    "overrides",
    "search",
    "upload",
]
