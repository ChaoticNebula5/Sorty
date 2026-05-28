import uuid
from datetime import datetime

from pydantic import BaseModel


class ExportCreateRequest(BaseModel):
    include_duplicates: bool = False
    include_blurry: bool = True
    include_pending: bool = False


class ExportJobRead(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    status: str
    export_type: str
    included_count: int
    excluded_count: int
    include_duplicates: bool
    include_blurry: bool
    include_pending: bool
    download_url: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
