import uuid
from decimal import Decimal

from app.schemas.ai import FolderSuggestion, ImageAnalysisResult
from app.services import analysis_service


class FakeDb:
    def __init__(self) -> None:
        self.added = None
        self.committed = False
        self.refreshed = False

    def scalar(self, statement):
        return None

    def add(self, item: object) -> None:
        self.added = item

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item: object) -> None:
        self.refreshed = True


def test_upsert_ai_analysis_creates_analysis() -> None:
    db = FakeDb()
    media_id = uuid.uuid4()
    result = ImageAnalysisResult(
        caption="A stage performance.",
        primary_subject="stage performance",
        scene_type="performance",
        people_count="group",
        event_context="cultural",
        tags=["stage", "students"],
        folder_suggestion=FolderSuggestion(
            primary_folder="Performances",
            sub_folder="Stage",
            confidence=0.88,
            reason="The image appears to show a stage performance.",
        ),
    )

    analysis = analysis_service.upsert_ai_analysis(
        db,
        media_id=media_id,
        result=result,
        model_provider="mock",
        model_name="mock-vision-v1",
        raw_response={"caption": result.caption},
    )

    assert analysis is db.added
    assert analysis.media_id == media_id
    assert analysis.caption == "A stage performance."
    assert analysis.tags == ["stage", "students"]
    assert analysis.suggested_primary_folder == "Performances"
    assert analysis.folder_confidence == Decimal("0.88")
    assert analysis.validation_status == "valid"
    assert db.committed is True
    assert db.refreshed is True
