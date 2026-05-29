import json
from types import SimpleNamespace

from PIL import Image

import app.services.vision_service as vision_service
from app.schemas.ai import ImageAnalysisResult
from app.services.vision_service import GeminiVisionProvider, MockVisionProvider


def test_mock_vision_provider_returns_valid_analysis(tmp_path) -> None:
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"image")

    result = MockVisionProvider().analyze_image(
        str(image_path),
        event_context={
            "name": "Cultural Fest",
            "event_type": "cultural",
        },
    )

    assert isinstance(result, ImageAnalysisResult)
    assert result.caption == "Mock analysis for photo.jpg from Cultural Fest."
    assert result.scene_type == "cultural"
    assert result.folder_suggestion.primary_folder == "Highlights"
    assert result.folder_suggestion.confidence == 0.75


def test_gemini_vision_provider_parses_response(monkeypatch, tmp_path) -> None:
    payload = {
        "caption": "Gemini caption",
        "primary_subject": "event moment",
        "scene_type": "event",
        "people_count": "unknown",
        "event_context": "event",
        "tags": ["event", "gemini"],
        "folder_suggestion": {
            "primary_folder": "Highlights",
            "sub_folder": "General",
            "confidence": 0.85,
            "reason": "Test response.",
        },
        "needs_review": False,
        "review_reasons": [],
    }

    class FakeModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def generate_content(self, inputs):
            return SimpleNamespace(text=json.dumps(payload))

    class FakeGenAi:
        def configure(self, api_key: str) -> None:
            self.api_key = api_key

        def GenerativeModel(self, model_name: str):
            return FakeModel(model_name)

    monkeypatch.setattr(vision_service, "_load_gemini_sdk", lambda: FakeGenAi())
    monkeypatch.setattr(
        vision_service,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_vision_model="gemini-test",
            gemini_api_key="test-key",
        ),
    )

    image_path = tmp_path / "photo.jpg"
    Image.new("RGB", (12, 12), color=(120, 140, 160)).save(image_path, format="JPEG")

    result = GeminiVisionProvider().analyze_image(
        str(image_path),
        event_context={"name": "Test", "event_type": "demo"},
    )

    assert isinstance(result, ImageAnalysisResult)
    assert result.caption == "Gemini caption"
    assert result.primary_subject == "event moment"
    assert result.scene_type == "event"
    assert result.people_count == "unknown"
    assert result.event_context == "event"
    assert isinstance(result.tags, list)
    assert result.tags == ["event", "gemini"]
    assert result.folder_suggestion is not None
    assert result.folder_suggestion.primary_folder == "Highlights"
    assert result.folder_suggestion.sub_folder == "General"
    assert result.folder_suggestion.confidence == 0.85
    assert result.folder_suggestion.reason == "Test response."
    assert result.needs_review is False
    assert result.review_reasons == []
