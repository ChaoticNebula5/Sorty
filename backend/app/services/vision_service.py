from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings
from app.schemas.ai import FolderSuggestion, ImageAnalysisResult


class VisionProvider(Protocol):
    provider_name: str
    model_name: str

    def analyze_image(
        self,
        image_path: str,
        event_context: dict[str, Any],
    ) -> ImageAnalysisResult:
        ...


class MockVisionProvider:
    provider_name = "mock"
    model_name = "mock-vision-v1"

    def analyze_image(
        self,
        image_path: str,
        event_context: dict[str, Any],
    ) -> ImageAnalysisResult:
        event_type = str(event_context.get("event_type") or "event")
        event_name = str(event_context.get("name") or "event")
        filename = Path(image_path).name

        return ImageAnalysisResult(
            caption=f"Mock analysis for {filename} from {event_name}.",
            primary_subject="event moment",
            scene_type=event_type,
            people_count="unknown",
            event_context=event_type,
            tags=["event", event_type, "mock-analysis"],
            folder_suggestion=FolderSuggestion(
                primary_folder="Highlights",
                sub_folder="General",
                confidence=0.75,
                reason="Mock provider returns a deterministic general event category.",
            ),
            needs_review=False,
            review_reasons=[],
        )


def get_vision_provider() -> VisionProvider:
    settings = get_settings()
    if settings.vision_provider == "mock":
        return MockVisionProvider()

    raise ValueError(f"Unsupported vision provider: {settings.vision_provider}")
