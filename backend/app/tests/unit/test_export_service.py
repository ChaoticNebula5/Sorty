import uuid
import zipfile
from io import BytesIO
from types import SimpleNamespace

import pytest

from app.schemas.export import ExportCreateRequest
from app.services import export_service


class FakeStorage:
    def __init__(self) -> None:
        self.objects = {"originals/stage.jpg": b"image-bytes"}
        self.written = {}

    def get_bytes(self, object_key: str) -> bytes:
        return self.objects[object_key]

    def put_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        self.written[object_key] = (data, content_type)


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = False
        self.scalar_result = None

    def scalar(self, statement):
        return self.scalar_result

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item: object) -> None:
        self.refreshed = True


def make_media(**overrides: object) -> SimpleNamespace:
    media_id = uuid.uuid4()
    data = {
        "id": media_id,
        "event_id": uuid.uuid4(),
        "original_filename": "stage/photo?.jpg",
        "original_object_key": "originals/stage.jpg",
        "ai_analysis": SimpleNamespace(
            caption="A stage performance.",
            tags=["stage"],
            suggested_primary_folder="Performances",
            suggested_sub_folder="Stage",
        ),
        "review_decision": SimpleNamespace(
            status="approved",
            include_in_export=True,
            final_primary_folder="Highlights",
            final_sub_folder="Opening",
            final_tags=["featured"],
        ),
        "quality_signal": SimpleNamespace(quality_label="sharp"),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_sanitize_zip_segment_removes_path_separators() -> None:
    assert export_service.sanitize_zip_segment("../Bad:Folder", "Fallback") == "_Bad_Folder"
    assert export_service.sanitize_zip_segment("   ", "Fallback") == "Fallback"


def test_build_export_zip_bytes_adds_media_metadata_and_summary() -> None:
    event = SimpleNamespace(id=uuid.uuid4(), name="Cultural Fest")
    media = make_media()
    storage = FakeStorage()

    zip_bytes = export_service.build_export_zip_bytes(event, [media], storage)

    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
        assert "Highlights/Opening/0001-stage_photo_.jpg" in names
        assert "metadata.csv" in names
        assert "summary.md" in names
        assert archive.read("Highlights/Opening/0001-stage_photo_.jpg") == b"image-bytes"
        assert str(media.id) in archive.read("metadata.csv").decode()
        assert "Cultural Fest" in archive.read("summary.md").decode()


def test_build_export_zip_bytes_places_pending_media_under_needs_review() -> None:
    event = SimpleNamespace(id=uuid.uuid4(), name="Cultural Fest")
    media = make_media(
        review_decision=SimpleNamespace(
            status="pending",
            include_in_export=False,
            final_primary_folder=None,
            final_sub_folder=None,
            final_tags=[],
        )
    )
    storage = FakeStorage()

    zip_bytes = export_service.build_export_zip_bytes(event, [media], storage)

    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        assert "Needs_Review/General/0001-stage_photo_.jpg" in archive.namelist()


def test_build_metadata_csv_escapes_spreadsheet_formulas() -> None:
    csv_text = export_service.build_metadata_csv(
        [
            {
                "media_id": "media-id",
                "original_filename": "=cmd.jpg",
                "archive_path": "Folder/file.jpg",
                "review_status": "approved",
                "caption": "+SUM(1,1)",
                "tags": "@danger",
            }
        ]
    )

    assert "'=cmd.jpg" in csv_text
    assert "'+SUM(1,1)" in csv_text
    assert "'@danger" in csv_text


def test_should_include_media_in_export_respects_review_statuses() -> None:
    approved = make_media()
    rejected = make_media(
        review_decision=SimpleNamespace(status="rejected", include_in_export=True)
    )
    duplicate = make_media(
        review_decision=SimpleNamespace(status="duplicate", include_in_export=False)
    )
    pending = make_media(
        review_decision=SimpleNamespace(status="pending", include_in_export=False)
    )
    blurry = make_media(
        quality_signal=SimpleNamespace(quality_label="blurry"),
    )

    default_payload = ExportCreateRequest()
    permissive_payload = ExportCreateRequest(
        include_duplicates=True,
        include_pending=True,
        include_blurry=True,
    )

    assert export_service.should_include_media_in_export(approved, default_payload) is True
    assert export_service.should_include_media_in_export(rejected, permissive_payload) is False
    assert export_service.should_include_media_in_export(duplicate, default_payload) is False
    assert export_service.should_include_media_in_export(duplicate, permissive_payload) is True
    assert export_service.should_include_media_in_export(pending, default_payload) is False
    assert export_service.should_include_media_in_export(pending, permissive_payload) is True
    assert (
        export_service.should_include_media_in_export(
            blurry,
            ExportCreateRequest(include_blurry=False),
        )
        is False
    )


def test_create_export_blocks_pending_reviews(monkeypatch) -> None:
    event = SimpleNamespace(id=uuid.uuid4(), name="Event")

    monkeypatch.setattr(export_service, "count_pending_reviews", lambda db, event_id: 1)

    with pytest.raises(export_service.ExportBlockedError):
        export_service.create_and_generate_export(
            db=object(),
            event=event,
            payload=ExportCreateRequest(),
            storage=FakeStorage(),
        )


def test_generate_export_archive_marks_failed_and_reraises(monkeypatch) -> None:
    db = FakeDb()
    db.scalar_result = SimpleNamespace(id=uuid.uuid4(), name="Event")
    export_job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=db.scalar_result.id,
        include_duplicates=False,
        include_blurry=True,
        include_pending=False,
        zip_object_key="events/event-id/exports/export-id.zip",
        status="exporting",
        error_message=None,
        completed_at=None,
    )

    monkeypatch.setattr(export_service, "list_export_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        export_service,
        "build_export_zip_bytes",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("zip failed")),
    )

    with pytest.raises(RuntimeError):
        export_service.generate_export_archive(db, export_job, FakeStorage())

    assert export_job.status == "failed"
    assert export_job.error_message == "zip failed"
    assert export_job.completed_at is not None
    assert db.committed is True
    assert db.refreshed is True
