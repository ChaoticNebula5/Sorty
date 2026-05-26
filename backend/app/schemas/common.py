from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class APIResponse(BaseModel):
    data: Any | None = None
    error: ErrorDetail | None = None


class Pagination(BaseModel):
    limit: int
    offset: int
    total: int


class APIListResponse(BaseModel):
    data: list[Any]
    pagination: Pagination
    error: ErrorDetail | None = None
