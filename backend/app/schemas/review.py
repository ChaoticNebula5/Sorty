import uuid

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError


class ReviewQueueItem(BaseModel):
    media_id: uuid.UUID
    thumbnail_url: str
    caption: str | None
    tags: list[str]
    suggested_primary_folder: str | None
    suggested_sub_folder: str | None
    quality_label: str | None = None
    is_duplicate: bool = False
    duplicate_group_id: uuid.UUID | None = None
    review_reasons: list[str]
    current_review_status: str


class ReviewDecisionUpdate(BaseModel):
    status: str = Field(pattern="^(approved|edited|rejected|duplicate)$")
    final_primary_folder: str | None = Field(default=None, max_length=120)
    final_sub_folder: str | None = Field(default=None, max_length=120)
    final_tags: list[str] = Field(default_factory=list, max_length=50)
    include_in_export: bool | None = None
    reviewer_note: str | None = Field(default=None, max_length=1000)

    @field_validator("final_primary_folder", "final_sub_folder", "reviewer_note")
    @classmethod
    def reject_blank_strings(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise PydanticCustomError("blank_string", "field cannot be blank")
        return value

    @field_validator("final_tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        for tag in value:
            if not tag.strip():
                raise PydanticCustomError("blank_tag", "tags cannot be blank")
            if len(tag) > 80:
                raise PydanticCustomError("tag_too_long", "tags must be 80 characters or fewer")
        return value

    @model_validator(mode="after")
    def validate_review_decision(self):
        if self.status in {"approved", "edited"} and not self.final_primary_folder:
            raise PydanticCustomError(
                "missing_final_primary_folder",
                "approved or edited media requires final_primary_folder",
            )
        if self.status in {"rejected", "duplicate"}:
            if self.include_in_export is True:
                raise PydanticCustomError(
                    "excluded_media_cannot_export",
                    "rejected or duplicate media cannot be included in export",
                )
            if self.final_primary_folder or self.final_sub_folder or self.final_tags:
                raise PydanticCustomError(
                    "excluded_media_cannot_have_folder",
                    "rejected or duplicate media cannot have final folder values",
                )
        return self


class ReviewDecisionRead(BaseModel):
    media_id: uuid.UUID
    status: str
    final_primary_folder: str | None
    final_sub_folder: str | None
    final_tags: list[str]
    include_in_export: bool
    review_reasons: list[str]
    reviewer_note: str | None


class BulkApproveReviewRequest(BaseModel):
    media_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    reviewer_note: str | None = Field(default=None, max_length=1000)

    @field_validator("media_ids")
    @classmethod
    def reject_duplicate_media_ids(
        cls,
        value: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        if len(value) != len(set(value)):
            raise PydanticCustomError(
                "duplicate_media_ids",
                "media_ids cannot contain duplicates",
            )
        return value

    @field_validator("reviewer_note")
    @classmethod
    def reject_blank_reviewer_note(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise PydanticCustomError("blank_string", "field cannot be blank")
        return value


class BulkApproveReviewResponse(BaseModel):
    event_id: uuid.UUID
    approved_count: int
    media_ids: list[uuid.UUID]
