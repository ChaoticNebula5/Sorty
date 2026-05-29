import json
import re
from pathlib import Path
from typing import Any, Protocol

from PIL import Image
from pydantic import ValidationError

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


class GeminiVisionProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.gemini_vision_model
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required when VISION_PROVIDER=gemini.")

        self._genai = _load_gemini_sdk()
        self._genai.configure(api_key=self.api_key)
        self._model = self._genai.GenerativeModel(self.model_name)

    def analyze_image(
        self,
        image_path: str,
        event_context: dict[str, Any],
    ) -> ImageAnalysisResult:
        prompt = _build_gemini_prompt(event_context)
        with Image.open(image_path) as image:
            image.load()
            response = self._model.generate_content([prompt, image])

        raw_text = getattr(response, "text", None) or ""
        payload = _extract_json_payload(raw_text)
        try:
            return ImageAnalysisResult.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(
                "Gemini response did not match ImageAnalysisResult schema."
            ) from exc


def _load_gemini_sdk():
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ValueError(
            "Gemini provider requires google-generativeai. "
            "Install with `pip install google-generativeai`."
        ) from exc
    return genai


def _build_gemini_prompt(event_context: dict[str, Any]) -> str:
    event_name = str(event_context.get("name") or "unknown")
    event_type = str(event_context.get("event_type") or "unknown")

    return "\n".join(
        [
            "You analyze event photos for a media archive.",
            "Return a JSON object that matches this schema:",
            "{",
            '  "caption": string,',
            '  "primary_subject": string | null,',
            '  "scene_type": string | null,',
            '  "people_count": string | null,',
            '  "event_context": string | null,',
            '  "tags": string[],',
            '  "folder_suggestion": {',
            '    "primary_folder": string,',
            '    "sub_folder": string | null,',
            '    "confidence": number (0 to 1),',
            '    "reason": string',
            "  },",
            '  "needs_review": boolean,',
            '  "review_reasons": string[]',
            "}",
            f"Event name: {event_name}",
            f"Event type: {event_type}",
            "Only output JSON. Do not include markdown or extra text.",
        ]
    )


def _extract_json_payload(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Gemini response was empty.")

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Gemini response did not contain JSON.")
        return json.loads(match.group(0))


def get_vision_provider() -> VisionProvider:
    settings = get_settings()
    if settings.vision_provider == "mock":
        return MockVisionProvider()
    if settings.vision_provider == "gemini":
        return GeminiVisionProvider()

    raise ValueError(f"Unsupported vision provider: {settings.vision_provider}")
