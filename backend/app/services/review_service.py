import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewDecision


def create_pending_review_decision(
    db: Session,
    media_id: uuid.UUID,
    review_reasons: list[str],
    commit: bool = True,
) -> ReviewDecision:
    decision = db.scalar(
        select(ReviewDecision).where(ReviewDecision.media_id == media_id)
    )
    if decision is None:
        decision = ReviewDecision(media_id=media_id)
        db.add(decision)

    decision.status = "pending"
    decision.include_in_export = False
    decision.review_reasons = review_reasons
    if commit:
        db.commit()
        db.refresh(decision)

    return decision
