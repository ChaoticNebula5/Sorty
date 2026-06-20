import json
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

import app.services.vision_service as vision_service
from app.schemas.ai import ImageAnalysisResult
from app.services.vision_service import (
    GeminiVisionProvider,
    MockVisionProvider,
    OllamaVisionProvider,
)


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


def test_ollama_vision_provider_posts_image_and_parses_response(monkeypatch, tmp_path) -> None:
    payload = {
        "caption": "Ollama caption",
        "primary_subject": "speaker",
        "scene_type": "talk",
        "people_count": "1",
        "event_context": "conference",
        "tags": ["speaker", "stage"],
        "folder_suggestion": {
            "primary_folder": "Talks",
            "sub_folder": "Keynotes",
            "confidence": 0.9,
            "reason": "A person is speaking on stage.",
        },
        "needs_review": False,
        "review_reasons": [],
    }
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"response": json.dumps(payload)}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(vision_service.httpx, "post", fake_post)
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"image-bytes")

    result = OllamaVisionProvider(
        base_url="http://localhost:11434",
        model_name="llava",
        timeout_seconds=3,
    ).analyze_image(str(image_path), {"name": "Conf", "event_type": "conference"})

    assert isinstance(result, ImageAnalysisResult)
    assert result.caption == "Ollama caption"
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["timeout"] == 3
    body = captured["json"]
    assert body["model"] == "llava"
    assert body["stream"] is False
    assert body["format"] == "json"
    assert body["images"] == ["aW1hZ2UtYnl0ZXM="]


def test_ollama_vision_provider_rejects_empty_response(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"response": ""}

    monkeypatch.setattr(vision_service.httpx, "post", lambda *args, **kwargs: FakeResponse())
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"image")

    with pytest.raises(ValueError, match="Ollama response was empty"):
        OllamaVisionProvider(base_url="http://localhost:11434").analyze_image(
            str(image_path),
            {},
        )


def test_ollama_vision_provider_rejects_invalid_json(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"response": "not json"}

    monkeypatch.setattr(vision_service.httpx, "post", lambda *args, **kwargs: FakeResponse())
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"image")

    with pytest.raises(ValueError, match="Ollama response did not contain JSON"):
        OllamaVisionProvider(base_url="http://localhost:11434").analyze_image(
            str(image_path),
            {},
        )


def test_ollama_vision_provider_rejects_schema_mismatch(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {"response": json.dumps({"caption": "missing folder"})}

    monkeypatch.setattr(vision_service.httpx, "post", lambda *args, **kwargs: FakeResponse())
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"image")

    with pytest.raises(ValueError, match="Ollama response did not match"):
        OllamaVisionProvider(base_url="http://localhost:11434").analyze_image(
            str(image_path),
            {},
        )


def test_ollama_vision_provider_reports_connection_failure(monkeypatch, tmp_path) -> None:
    def fake_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(vision_service.httpx, "post", fake_post)
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"image")

    with pytest.raises(ValueError, match="Could not connect to Ollama"):
        OllamaVisionProvider(base_url="http://localhost:11434").analyze_image(
            str(image_path),
            {},
        )


def test_get_vision_provider_supports_ollama(monkeypatch) -> None:
    monkeypatch.setattr(
        vision_service,
        "get_settings",
        lambda: SimpleNamespace(
            vision_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_vision_model="llava",
        ),
    )

    provider = vision_service.get_vision_provider()

    assert isinstance(provider, OllamaVisionProvider)
    assert provider.model_name == "llava"
