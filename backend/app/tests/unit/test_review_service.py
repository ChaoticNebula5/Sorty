import uuid
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.db.models import ReviewDecision
from app.schemas.review import ReviewDecisionUpdate
from app.services import review_service


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = False

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item: object) -> None:
        self.refreshed = True


def test_apply_review_decision_marks_approved_media_processed() -> None:
    db = FakeDb()
    media = SimpleNamespace(processing_status="needs_review", processing_error="low")
    decision = SimpleNamespace(
        media=media,
        status="pending",
        final_primary_folder=None,
        final_sub_folder=None,
        final_tags=[],
        include_in_export=False,
        reviewer_note=None,
        reviewed_at=None,
    )
    payload = ReviewDecisionUpdate(
        status="approved",
        final_primary_folder="Performances",
        final_sub_folder="Stage",
        final_tags=["stage"],
        include_in_export=None,
        reviewer_note="Good image.",
    )

    result = review_service.apply_review_decision(db, decision, payload)

    assert result is decision
    assert decision.status == "approved"
    assert decision.final_primary_folder == "Performances"
    assert decision.include_in_export is True
    assert decision.reviewed_at is not None
    assert media.processing_status == "processed"
    assert media.processing_error is None
    assert db.committed is True
    assert db.refreshed is True


def test_apply_review_decision_marks_rejected_media_excluded() -> None:
    db = FakeDb()
    media = SimpleNamespace(processing_status="needs_review", processing_error=None)
    decision = SimpleNamespace(
        media=media,
        status="pending",
        final_primary_folder=None,
        final_sub_folder=None,
        final_tags=[],
        include_in_export=False,
        reviewer_note=None,
        reviewed_at=None,
    )
    payload = ReviewDecisionUpdate(status="rejected", include_in_export=False)

    review_service.apply_review_decision(db, decision, payload)

    assert decision.status == "rejected"
    assert decision.include_in_export is False
    assert media.processing_status == "excluded"
    assert db.committed is True


def test_lock_review_decision_uses_for_update() -> None:
    captured = {}

    class FakeDb:
        def scalar(self, statement):
            captured["statement"] = statement
            return None

    decision_id = uuid.uuid4()

    result = review_service._lock_review_decision(
        FakeDb(),
        SimpleNamespace(id=decision_id),
    )

    compiled = str(
        captured["statement"].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert result is None
    assert "FOR UPDATE OF review_decisions" in compiled
    assert str(decision_id) in compiled
    assert ReviewDecision.__tablename__ in compiled
