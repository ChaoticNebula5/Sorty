import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AIAnalysis
from app.schemas.ai import ImageAnalysisResult


def upsert_ai_analysis(
    db: Session,
    media_id: uuid.UUID,
    result: ImageAnalysisResult,
    model_provider: str,
    model_name: str,
    raw_response: dict | None = None,
    commit: bool = True,
) -> AIAnalysis:
    analysis = db.scalar(select(AIAnalysis).where(AIAnalysis.media_id == media_id))
    if analysis is None:
        analysis = AIAnalysis(media_id=media_id)
        db.add(analysis)

    folder = result.folder_suggestion
    analysis.caption = result.caption
    analysis.primary_subject = result.primary_subject
    analysis.scene_type = result.scene_type
    analysis.people_count = result.people_count
    analysis.event_context = result.event_context
    analysis.tags = result.tags
    analysis.suggested_primary_folder = folder.primary_folder
    analysis.suggested_sub_folder = folder.sub_folder
    analysis.folder_confidence = Decimal(str(folder.confidence))
    analysis.folder_reason = folder.reason
    analysis.model_provider = model_provider
    analysis.model_name = model_name
    analysis.raw_response = raw_response
    analysis.validation_status = "valid"
    analysis.validation_error = None

    if commit:
        db.commit()
        db.refresh(analysis)

    return analysis
