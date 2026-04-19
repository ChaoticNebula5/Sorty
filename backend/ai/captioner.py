"""
Gemini captioning utilities for Sorty.
Generates captions, tags, category scores, and sponsor visibility in one pass.
"""

import json
import re

import google.generativeai as genai

from backend.config import settings


CAPTION_PROMPT = """
You are analyzing a single event photo for media organization.

Return strict JSON with this shape:
{
  "caption": "short factual caption",
  "tags": ["tag1", "tag2"],
  "primary_category": "stage|crowd|team|performance|portrait|other",
  "category_scores": {
    "stage": 0.0,
    "crowd": 0.0,
    "team": 0.0,
    "performance": 0.0,
    "portrait": 0.0,
    "other": 0.0
  },
  "sponsor_visible_score": 0.0
}

Rules:
- Be concise and factual.
- Tags should be short, lowercase, and useful for search.
- Category scores must be floats between 0.0 and 1.0.
- Primary category must be the highest-confidence category.
- sponsor_visible_score must be a float between 0.0 and 1.0 representing how clearly sponsor branding, banners, logos, or signage are visible.
- Do not include markdown fences.
""".strip()


class GeminiCaptioner:
    """Wrapper around Gemini Vision for semantic enrichment generation."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for caption generation")
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_vision_model)

    def caption_image_bytes(self, image_bytes: bytes, mime_type: str) -> dict:
        """Generate caption, tags, category scores, and sponsor score for an image."""
        response = self.model.generate_content(
            [
                CAPTION_PROMPT,
                {
                    "mime_type": mime_type,
                    "data": image_bytes,
                },
            ]
        )

        text = self._extract_json_text(response.text)
        return json.loads(text)

    @staticmethod
    def _extract_json_text(text: str | None) -> str:
        """Extract raw JSON text from a Gemini response."""
        if not text:
            raise ValueError("Gemini returned an empty response")

        cleaned = text.strip()
        cleaned = re.sub(
            r"^```json\s*|^```\s*|\s*```$", "", cleaned, flags=re.MULTILINE
        )
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Gemini did not return valid JSON")
        return cleaned[start : end + 1]


_captioner: GeminiCaptioner | None = None


def get_captioner() -> GeminiCaptioner:
    """Return a singleton Gemini captioner instance."""
    global _captioner
    if _captioner is None:
        _captioner = GeminiCaptioner()
    return _captioner
