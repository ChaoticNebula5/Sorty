"""
Export request/response schemas.
See PRD section 9.6 (Export API).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from backend.models import ExportStatus


class ExportResponseData(BaseModel):
    """Response payload for export creation."""

    export_id: UUID
    status: ExportStatus
    estimated_size_bytes: int
    asset_count: int


class ExportResponse(BaseModel):
    """Response schema for starting an export."""

    data: ExportResponseData


class ExportStatusResponseData(BaseModel):
    """Response payload for export status polling."""

    export_id: UUID
    status: ExportStatus
    download_url: str | None = None
    expires_at: datetime | None = None
    size_bytes: int | None = None


class ExportStatusResponse(BaseModel):
    """Response schema for export status endpoint."""

    data: ExportStatusResponseData
