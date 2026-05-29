import uuid
from types import SimpleNamespace

import pytest

from app.schemas.ai import FolderSuggestion, ImageAnalysisResult
from app.agents.mediaops_graph import MediaOpsGraphResult
from worker import tasks


class FakeSession:
    def __init__(self) -> None:
        self.rolled_back = False
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def rollback(self) -> None:
        self.rolled_back = True

    def commit(self) -> None:
        self.committed = True

    def refresh(self, item: object) -> None:
        return None


class FakeStorage:
    def __init__(self, temp_path) -> None:
        self.temp_path = temp_path

    def download_to_temp(self, object_key: str):
        self.temp_path.write_bytes(b"image")
        return self.temp_path


class FakeVisionProvider:
    provider_name = "mock"
    model_name = "mock-vision-v1"

    def analyze_image(self, image_path: str, event_context: dict) -> ImageAnalysisResult:
        self.event_context = event_context
        return ImageAnalysisResult(
            caption="Mock caption",
            primary_subject="event moment",
            scene_type="event",
            people_count="unknown",
            event_context="event",
            tags=["event"],
            folder_suggestion=FolderSuggestion(
                primary_folder="Highlights",
                sub_folder="General",
                confidence=0.75,
                reason="Mock result.",
            ),
        )


@pytest.fixture(autouse=True)
def fake_quality_service(monkeypatch) -> None:
    quality_result = SimpleNamespace(
        blur_score=240.0,
        quality_label="sharp",
        image_width=100,
        image_height=100,
        perceptual_hash="0" * 16,
    )
    quality_signal = SimpleNamespace(quality_label="sharp", is_duplicate=False)
    duplicate_result = SimpleNamespace(is_duplicate=False, duplicate_distance=None)

    monkeypatch.setattr(
        tasks.quality_service,
        "analyze_image_quality",
        lambda image_path: quality_result,
    )
    monkeypatch.setattr(
        tasks.quality_service,
        "upsert_quality_signal",
        lambda db, media_id, result, commit=True: quality_signal,
    )
    monkeypatch.setattr(
        tasks.quality_service,
        "detect_duplicate_for_media",
        lambda db,
        media_id,
        event_id,
        perceptual_hash,
        batch_job_id=None,
        quality_signal=None,
        commit=True: duplicate_result,
    )
    monkeypatch.setattr(
        tasks.review_service,
        "create_auto_approved_review_decision",
        lambda db, media, commit=True: SimpleNamespace(
            status="approved",
            include_in_export=True,
        ),
    )


def test_process_batch_job_marks_job_media_and_analysis_completed(
    monkeypatch,
    tmp_path,
) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        original_object_key="events/event-id/originals/media-id.jpg",
    )
    calls: list[str] = []

    provider = FakeVisionProvider()

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        tasks.event_service,
        "get_event",
        lambda db, event_id: SimpleNamespace(name="Cultural Fest", event_type="cultural"),
    )
    monkeypatch.setattr(
        tasks.storage_factory,
        "get_storage_service",
        lambda: FakeStorage(tmp_path / "image.jpg"),
    )
    monkeypatch.setattr(
        tasks.vision_service,
        "get_vision_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_processing",
        lambda db, job: calls.append("job_processing"),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "list_batch_media",
        lambda db, job_id, media_ids=None: [media],
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_processing",
        lambda db, media: calls.append("single_media_processing"),
    )
    monkeypatch.setattr(
        tasks.analysis_service,
        "upsert_ai_analysis",
        lambda *args, **kwargs: calls.append("analysis_saved"),
    )
    monkeypatch.setattr(
        tasks.review_service,
        "create_auto_approved_review_decision",
        lambda db, media, commit=True: calls.append("auto_review_saved")
        or SimpleNamespace(status="approved", include_in_export=True),
    )
    monkeypatch.setattr(
        tasks.search_service,
        "upsert_media_embedding",
        lambda db, media, commit=True: calls.append("embedding_saved"),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_processed",
        lambda db, media, commit=True: calls.append("single_media_processed"),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_finished",
        lambda db, job, processed_files, failed_files, needs_review_count: calls.append(
            f"job_finished:{processed_files}:{failed_files}:{needs_review_count}"
        ),
    )
    monkeypatch.setattr(
        tasks,
        "run_mediaops_batch",
        lambda **kwargs: calls.append(f"graph:{kwargs['needs_review_count']}"),
    )

    result = tasks.process_batch_job({"job_id": str(job.id)})

    assert result == str(job.id)
    assert calls == [
        "job_processing",
        "single_media_processing",
        "analysis_saved",
        "auto_review_saved",
        "single_media_processed",
        "embedding_saved",
        "job_finished:1:0:0",
        "graph:0",
    ]
    assert provider.event_context == {
        "event_id": str(job.event_id),
        "name": "Cultural Fest",
        "event_type": "cultural",
    }


def test_process_batch_job_reuses_quality_signal_for_duplicate_detection(
    monkeypatch,
    tmp_path,
) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=job.event_id,
        original_object_key="events/event-id/originals/photo.jpg",
    )
    quality_signal = SimpleNamespace(quality_label="sharp", is_duplicate=False)
    captured: dict[str, object] = {}

    def fake_detect_duplicate(
        db,
        media_id,
        event_id,
        perceptual_hash,
        batch_job_id=None,
        quality_signal=None,
        commit=True,
    ):
        captured["quality_signal"] = quality_signal
        return SimpleNamespace(is_duplicate=False, duplicate_distance=None)

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.event_service, "get_event", lambda db, event_id: None)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks.storage_factory,
        "get_storage_service",
        lambda: FakeStorage(tmp_path / "photo.jpg"),
    )
    monkeypatch.setattr(
        tasks.vision_service,
        "get_vision_provider",
        lambda: FakeVisionProvider(),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "list_batch_media",
        lambda db, job_id, media_ids=None: [media],
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_processing",
        lambda db, media: None,
    )
    monkeypatch.setattr(
        tasks.analysis_service,
        "upsert_ai_analysis",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        tasks.quality_service,
        "upsert_quality_signal",
        lambda db, media_id, result, commit=True: quality_signal,
    )
    monkeypatch.setattr(
        tasks.quality_service,
        "detect_duplicate_for_media",
        fake_detect_duplicate,
    )
    monkeypatch.setattr(
        tasks.search_service,
        "upsert_media_embedding",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_processed",
        lambda db, media, commit=True: None,
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_finished",
        lambda db, job, processed_files, failed_files, needs_review_count: None,
    )
    monkeypatch.setattr(tasks, "run_mediaops_batch", lambda **kwargs: None)

    tasks.process_batch_job({"job_id": str(job.id)})

    assert captured["quality_signal"] is quality_signal


def test_process_batch_job_sends_blurry_media_to_review(monkeypatch, tmp_path) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=job.event_id,
        original_object_key="events/event-id/originals/blurry.jpg",
    )
    quality_result = SimpleNamespace(
        blur_score=10.0,
        quality_label="blurry",
        image_width=100,
        image_height=100,
        perceptual_hash="0" * 16,
    )
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.event_service, "get_event", lambda db, event_id: None)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks.storage_factory,
        "get_storage_service",
        lambda: FakeStorage(tmp_path / "blurry.jpg"),
    )
    monkeypatch.setattr(
        tasks.vision_service,
        "get_vision_provider",
        lambda: FakeVisionProvider(),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "list_batch_media",
        lambda db, job_id, media_ids=None: [media],
    )
    monkeypatch.setattr(tasks.media_service, "mark_media_processing", lambda db, media: None)
    monkeypatch.setattr(tasks.analysis_service, "upsert_ai_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tasks.quality_service,
        "analyze_image_quality",
        lambda image_path: quality_result,
    )
    monkeypatch.setattr(
        tasks.quality_service,
        "upsert_quality_signal",
        lambda db, media_id, result, commit=True: SimpleNamespace(
            quality_label=result.quality_label,
        ),
    )
    monkeypatch.setattr(tasks.search_service, "upsert_media_embedding", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tasks.review_service,
        "create_pending_review_decision",
        lambda db, media_id, review_reasons, commit=True: calls.append(
            f"review:{','.join(review_reasons)}"
        ),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_needs_review",
        lambda db, media, reason=None, commit=True: calls.append(
            f"needs_review:{reason}"
        ),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_finished",
        lambda db, job, processed_files, failed_files, needs_review_count: calls.append(
            f"finished:{processed_files}:{failed_files}:{needs_review_count}"
        ),
    )
    monkeypatch.setattr(
        tasks,
        "run_mediaops_batch",
        lambda **kwargs: calls.append("graph"),
    )

    result = tasks.process_batch_job({"job_id": str(job.id)})

    assert result == str(job.id)
    assert calls == [
        "review:low_quality_blur",
        "needs_review:low_quality_blur",
        "finished:0:0:1",
        "graph",
    ]


def test_process_batch_job_sends_duplicate_media_to_review(monkeypatch, tmp_path) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=job.event_id,
        original_object_key="events/event-id/originals/duplicate.jpg",
    )
    duplicate_result = SimpleNamespace(is_duplicate=True, duplicate_distance=2)
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.event_service, "get_event", lambda db, event_id: None)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks.storage_factory,
        "get_storage_service",
        lambda: FakeStorage(tmp_path / "duplicate.jpg"),
    )
    monkeypatch.setattr(
        tasks.vision_service,
        "get_vision_provider",
        lambda: FakeVisionProvider(),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "list_batch_media",
        lambda db, job_id, media_ids=None: [media],
    )
    monkeypatch.setattr(tasks.media_service, "mark_media_processing", lambda db, media: None)
    monkeypatch.setattr(tasks.analysis_service, "upsert_ai_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tasks.quality_service,
        "detect_duplicate_for_media",
        lambda db,
        media_id,
        event_id,
        perceptual_hash,
        batch_job_id=None,
        quality_signal=None,
        commit=True: duplicate_result,
    )
    monkeypatch.setattr(tasks.search_service, "upsert_media_embedding", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tasks.review_service,
        "create_pending_review_decision",
        lambda db, media_id, review_reasons, commit=True: calls.append(
            f"review:{','.join(review_reasons)}"
        ),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_needs_review",
        lambda db, media, reason=None, commit=True: calls.append(
            f"needs_review:{reason}"
        ),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_finished",
        lambda db, job, processed_files, failed_files, needs_review_count: calls.append(
            f"finished:{processed_files}:{failed_files}:{needs_review_count}"
        ),
    )
    monkeypatch.setattr(
        tasks,
        "run_mediaops_batch",
        lambda **kwargs: calls.append("graph"),
    )

    result = tasks.process_batch_job({"job_id": str(job.id)})

    assert result == str(job.id)
    assert calls == [
        "review:possible_duplicate",
        "needs_review:possible_duplicate",
        "finished:0:0:1",
        "graph",
    ]


def test_process_batch_job_marks_job_and_media_failed(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    calls: list[str] = []

    def fail_storage():
        raise RuntimeError("storage setup failed")

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(tasks.storage_factory, "get_storage_service", fail_storage)
    monkeypatch.setattr(
        tasks.media_service,
        "mark_batch_media_failed",
        lambda db, job_id, error_message: calls.append("media_failed"),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_failed",
        lambda db, job, error_message: calls.append("job_failed"),
    )

    with pytest.raises(RuntimeError):
        tasks.process_batch_job({"job_id": str(job.id)})

    assert fake_db.rolled_back is True
    assert calls == ["media_failed", "job_failed"]


def test_process_batch_job_marks_partial_failed_for_single_media_failure(
    monkeypatch,
    tmp_path,
) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    first_media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        original_object_key="events/event-id/originals/first.jpg",
    )
    second_media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        original_object_key="events/event-id/originals/second.jpg",
    )
    calls: list[str] = []

    class FailingProvider(FakeVisionProvider):
        def analyze_image(self, image_path: str, event_context: dict) -> ImageAnalysisResult:
            if len([call for call in calls if call == "provider_called"]) == 1:
                raise RuntimeError("vision failed")
            calls.append("provider_called")
            return super().analyze_image(image_path, event_context)

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.event_service, "get_event", lambda db, event_id: None)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks.storage_factory,
        "get_storage_service",
        lambda: FakeStorage(tmp_path / "image.jpg"),
    )
    monkeypatch.setattr(tasks.vision_service, "get_vision_provider", lambda: FailingProvider())
    monkeypatch.setattr(
        tasks.media_service,
        "list_batch_media",
        lambda db, job_id, media_ids=None: [first_media, second_media],
    )
    monkeypatch.setattr(tasks.media_service, "mark_media_processing", lambda db, media: None)
    monkeypatch.setattr(tasks.analysis_service, "upsert_ai_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks.search_service, "upsert_media_embedding", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_processed",
        lambda db, media, commit=True: calls.append(f"processed:{media.id}"),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_failed",
        lambda db, media, error_message: calls.append(f"failed:{media.id}"),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_finished",
        lambda db, job, processed_files, failed_files, needs_review_count: calls.append(
            f"finished:{processed_files}:{failed_files}:{needs_review_count}"
        ),
    )
    monkeypatch.setattr(tasks, "run_mediaops_batch", lambda **kwargs: calls.append("graph"))

    result = tasks.process_batch_job({"job_id": str(job.id)})

    assert result == str(job.id)
    assert f"processed:{first_media.id}" in calls
    assert f"failed:{second_media.id}" in calls
    assert "finished:1:1:0" in calls
    assert "graph" in calls


def test_process_batch_job_marks_media_needs_review(monkeypatch, tmp_path) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=job.event_id,
        original_object_key="events/event-id/originals/review.jpg",
    )
    calls: list[str] = []

    class ReviewProvider(FakeVisionProvider):
        def analyze_image(self, image_path: str, event_context: dict) -> ImageAnalysisResult:
            result = super().analyze_image(image_path, event_context)
            result.needs_review = True
            result.review_reasons = ["low_confidence"]
            return result

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.event_service, "get_event", lambda db, event_id: None)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks.storage_factory,
        "get_storage_service",
        lambda: FakeStorage(tmp_path / "review.jpg"),
    )
    monkeypatch.setattr(tasks.vision_service, "get_vision_provider", lambda: ReviewProvider())
    monkeypatch.setattr(tasks.media_service, "list_batch_media", lambda db, job_id, media_ids=None: [media])
    monkeypatch.setattr(tasks.media_service, "mark_media_processing", lambda db, media: None)
    monkeypatch.setattr(tasks.analysis_service, "upsert_ai_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks.search_service, "upsert_media_embedding", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tasks.review_service,
        "create_pending_review_decision",
        lambda db, media_id, review_reasons, commit=True: calls.append(
            f"review:{review_reasons[0]}"
        ),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_needs_review",
        lambda db, media, reason=None, commit=True: calls.append(
            f"needs_review:{reason}"
        ),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_finished",
        lambda db, job, processed_files, failed_files, needs_review_count: calls.append(
            f"finished:{processed_files}:{failed_files}:{needs_review_count}"
        ),
    )
    monkeypatch.setattr(tasks, "run_mediaops_batch", lambda **kwargs: calls.append("graph"))

    result = tasks.process_batch_job({"job_id": str(job.id), "media_ids": [str(media.id)]})

    assert result == str(job.id)
    assert calls == [
        "review:low_confidence",
        "needs_review:low_confidence",
        "finished:0:0:1",
        "graph",
    ]


def test_process_batch_job_ignores_payload_media_subset(monkeypatch, tmp_path) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    first_media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=job.event_id,
        original_object_key="events/event-id/originals/first.jpg",
    )
    second_media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=job.event_id,
        original_object_key="events/event-id/originals/second.jpg",
    )
    captured_filters: list[object] = []
    processed_media_ids: list[uuid.UUID] = []

    def fake_list_batch_media(db, job_id, media_ids=None):
        captured_filters.append(media_ids)
        return [first_media, second_media]

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.event_service, "get_event", lambda db, event_id: None)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks.storage_factory,
        "get_storage_service",
        lambda: FakeStorage(tmp_path / "subset.jpg"),
    )
    monkeypatch.setattr(tasks.vision_service, "get_vision_provider", lambda: FakeVisionProvider())
    monkeypatch.setattr(tasks.media_service, "list_batch_media", fake_list_batch_media)
    monkeypatch.setattr(tasks.media_service, "mark_media_processing", lambda db, media: None)
    monkeypatch.setattr(tasks.analysis_service, "upsert_ai_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks.search_service, "upsert_media_embedding", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_processed",
        lambda db, media, commit=True: processed_media_ids.append(media.id),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_finished",
        lambda db, job, processed_files, failed_files, needs_review_count: None,
    )
    monkeypatch.setattr(tasks, "run_mediaops_batch", lambda **kwargs: None)

    tasks.process_batch_job(
        {
            "job_id": str(job.id),
            "media_ids": [str(first_media.id)],
        }
    )

    assert captured_filters == [None]
    assert processed_media_ids == [first_media.id, second_media.id]


def test_process_batch_job_graph_failure_does_not_mark_media_failed(monkeypatch, tmp_path) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
    )
    media = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=job.event_id,
        original_object_key="events/event-id/originals/first.jpg",
    )
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.event_service, "get_event", lambda db, event_id: None)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks.storage_factory,
        "get_storage_service",
        lambda: FakeStorage(tmp_path / "graph.jpg"),
    )
    monkeypatch.setattr(tasks.vision_service, "get_vision_provider", lambda: FakeVisionProvider())
    monkeypatch.setattr(tasks.media_service, "list_batch_media", lambda db, job_id, media_ids=None: [media])
    monkeypatch.setattr(tasks.media_service, "mark_media_processing", lambda db, media: None)
    monkeypatch.setattr(tasks.analysis_service, "upsert_ai_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks.search_service, "upsert_media_embedding", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tasks.media_service,
        "mark_media_processed",
        lambda db, media, commit=True: calls.append("media_processed"),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_finished",
        lambda db, job, processed_files, failed_files, needs_review_count: job,
    )
    monkeypatch.setattr(
        tasks,
        "run_mediaops_batch",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("checkpoint down")),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_workflow_failed",
        lambda db, job, error_message: calls.append(error_message),
    )
    monkeypatch.setattr(
        tasks.media_service,
        "mark_batch_media_failed",
        lambda db, job_id, error_message: calls.append("batch_media_failed"),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_failed",
        lambda db, job, error_message: calls.append("job_failed"),
    )

    with pytest.raises(tasks.WorkflowCheckpointError):
        tasks.process_batch_job({"job_id": str(job.id)})

    assert "media_processed" in calls
    assert "Could not create LangGraph checkpoint: checkpoint down" in calls
    assert "batch_media_failed" not in calls
    assert "job_failed" not in calls


def test_process_batch_job_raises_for_missing_job(monkeypatch) -> None:
    fake_db = FakeSession()
    job_id = uuid.uuid4()

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: None)

    with pytest.raises(ValueError):
        tasks.process_batch_job({"job_id": str(job_id)})


def test_resume_batch_job_marks_placeholder_done(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
        status="queued",
    )
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_processing",
        lambda db, job: calls.append("processing"),
    )
    monkeypatch.setattr(
        tasks,
        "resume_reviewed_batch",
        lambda thread_id, job_id: (
            calls.append(f"graph:{thread_id}:{job_id}")
            or MediaOpsGraphResult(
                status="finalized",
                thread_id=thread_id,
                job_id=job_id,
                event_id=str(job.event_id),
                pending_review_count=0,
            )
        ),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_resume_placeholder_done",
        lambda db, job: calls.append("placeholder_done"),
    )

    result = tasks.resume_batch_job(
        {
            "job_id": str(job.id),
            "event_id": str(job.event_id),
            "thread_id": job.langgraph_thread_id,
            "mode": "resume",
        }
    )

    assert result == str(job.id)
    assert calls == ["processing", f"graph:thread-1:{job.id}", "placeholder_done"]


def test_resume_batch_job_rejects_unfinalized_graph_result(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
        status="queued",
    )
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks,
        "resume_reviewed_batch",
        lambda thread_id, job_id: MediaOpsGraphResult(
            status="interrupted_for_review",
            thread_id=thread_id,
            job_id=job_id,
            event_id=str(job.event_id),
            pending_review_count=1,
        ),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_resume_enqueue_failed",
        lambda db, job: calls.append("retryable"),
    )

    with pytest.raises(tasks.WorkflowResumeError):
        tasks.resume_batch_job(
            {
                "job_id": str(job.id),
                "event_id": str(job.event_id),
                "thread_id": job.langgraph_thread_id,
                "mode": "resume",
            }
        )

    assert calls == ["retryable"]


def test_resume_batch_job_rejects_mismatched_graph_result(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
        status="queued",
    )
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", lambda db, job: None)
    monkeypatch.setattr(
        tasks,
        "resume_reviewed_batch",
        lambda thread_id, job_id: MediaOpsGraphResult(
            status="finalized",
            thread_id=thread_id,
            job_id=str(uuid.uuid4()),
            event_id=str(job.event_id),
            pending_review_count=0,
        ),
    )
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_resume_enqueue_failed",
        lambda db, job: calls.append("retryable"),
    )

    with pytest.raises(tasks.WorkflowResumeError):
        tasks.resume_batch_job(
            {
                "job_id": str(job.id),
                "event_id": str(job.event_id),
                "thread_id": job.langgraph_thread_id,
                "mode": "resume",
            }
        )

    assert calls == ["retryable"]


def test_resume_batch_job_marks_failed_on_error(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
        status="queued",
    )
    calls: list[str] = []

    def fail_processing(db, job):
        raise RuntimeError("resume failed")

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(tasks.job_service, "mark_job_processing", fail_processing)
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_resume_enqueue_failed",
        lambda db, job: calls.append("retryable"),
    )

    with pytest.raises(RuntimeError):
        tasks.resume_batch_job(
            {
                "job_id": str(job.id),
                "event_id": str(job.event_id),
                "thread_id": job.langgraph_thread_id,
                "mode": "resume",
            }
        )

    assert fake_db.rolled_back is True
    assert calls == ["retryable"]


def test_resume_batch_job_rejects_wrong_thread_id(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
        status="queued",
    )

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)

    with pytest.raises(ValueError):
        tasks.resume_batch_job(
            {
                "job_id": str(job.id),
                "event_id": str(job.event_id),
                "thread_id": "wrong-thread",
                "mode": "resume",
            }
        )

    assert fake_db.rolled_back is True


def test_resume_batch_job_wrong_thread_restores_retryable_state(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
        status="queued",
    )
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_resume_enqueue_failed",
        lambda db, job: calls.append("retryable"),
    )

    with pytest.raises(ValueError):
        tasks.resume_batch_job(
            {
                "job_id": str(job.id),
                "event_id": str(job.event_id),
                "thread_id": "wrong-thread",
                "mode": "resume",
            }
        )

    assert fake_db.rolled_back is True
    assert calls == ["retryable"]


def test_resume_batch_job_rejects_wrong_mode(monkeypatch) -> None:
    fake_db = FakeSession()
    job = SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        langgraph_thread_id="thread-1",
        status="queued",
    )
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(tasks.job_service, "get_batch_job", lambda db, job_id: job)
    monkeypatch.setattr(
        tasks.job_service,
        "mark_job_resume_enqueue_failed",
        lambda db, job: calls.append("retryable"),
    )

    with pytest.raises(ValueError):
        tasks.resume_batch_job(
            {
                "job_id": str(job.id),
                "event_id": str(job.event_id),
                "thread_id": job.langgraph_thread_id,
                "mode": "start",
            }
        )

    assert fake_db.rolled_back is True
    assert calls == ["retryable"]


def test_generate_export_job_runs_export_pipeline(monkeypatch) -> None:
    fake_db = FakeSession()
    export_job = SimpleNamespace(id=uuid.uuid4(), status="queued")
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        tasks.export_service,
        "get_export_job",
        lambda db, export_id: export_job,
    )
    monkeypatch.setattr(
        tasks.export_service,
        "mark_export_exporting",
        lambda db, export_job: calls.append("exporting"),
    )
    monkeypatch.setattr(tasks.storage_factory, "get_storage_service", lambda: object())
    monkeypatch.setattr(
        tasks.export_service,
        "generate_export_archive",
        lambda db, export_job, storage: calls.append("archive"),
    )

    result = tasks.generate_export_job(
        {"export_id": str(export_job.id), "mode": "export"}
    )

    assert result == str(export_job.id)
    assert calls == ["exporting", "archive"]


def test_generate_export_job_marks_failed_on_error(monkeypatch) -> None:
    fake_db = FakeSession()
    export_job = SimpleNamespace(id=uuid.uuid4(), status="queued")
    calls: list[str] = []

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        tasks.export_service,
        "get_export_job",
        lambda db, export_id: export_job,
    )
    monkeypatch.setattr(tasks.export_service, "mark_export_exporting", lambda db, export_job: None)
    monkeypatch.setattr(tasks.storage_factory, "get_storage_service", lambda: object())
    monkeypatch.setattr(
        tasks.export_service,
        "generate_export_archive",
        lambda db, export_job, storage: (_ for _ in ()).throw(RuntimeError("zip failed")),
    )
    monkeypatch.setattr(
        tasks.export_service,
        "mark_export_failed",
        lambda db, export_job, error_message: calls.append(error_message),
    )

    with pytest.raises(RuntimeError):
        tasks.generate_export_job(
            {"export_id": str(export_job.id), "mode": "export"}
        )

    assert fake_db.rolled_back is True
    assert calls == ["zip failed"]
