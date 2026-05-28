from pydantic import BaseModel, Field


class FolderSuggestion(BaseModel):
    primary_folder: str
    sub_folder: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class ImageAnalysisResult(BaseModel):
    caption: str
    primary_subject: str | None = None
    scene_type: str | None = None
    people_count: str | None = None
    event_context: str | None = None
    tags: list[str] = Field(default_factory=list)
    folder_suggestion: FolderSuggestion
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
