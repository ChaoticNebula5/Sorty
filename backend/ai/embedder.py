"""
CLIP embedding utilities for Sorty.
Generates 512-dim normalized embeddings for images and text.
"""

from io import BytesIO
from pathlib import Path

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from backend.config import settings


class ClipEmbedder:
    """Wrapper around CLIP for image and text embeddings."""

    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = settings.clip_model_path
        self.cache_dir = settings.clip_cache_dir

        model_source = self._resolve_model_source(self.model_name)
        self.processor = CLIPProcessor.from_pretrained(
            model_source,
            cache_dir=self.cache_dir,
        )
        self.model = CLIPModel.from_pretrained(
            model_source,
            cache_dir=self.cache_dir,
        )
        self.model.to(self.device)
        self.model.eval()

    @staticmethod
    def _resolve_model_source(model_name: str) -> str:
        """Resolve configured model path or Hugging Face model id."""
        model_path = Path(model_name)
        if model_path.exists():
            return str(model_path)
        return model_name

    @torch.inference_mode()
    def embed_image_bytes(self, image_bytes: bytes) -> list[float]:
        """Generate a normalized embedding vector from image bytes."""
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        image_features = self.model.get_image_features(**inputs)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        return image_features[0].detach().cpu().tolist()

    @torch.inference_mode()
    def embed_text(self, text: str) -> list[float]:
        """Generate a normalized embedding vector from text."""
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        text_features = self.model.get_text_features(**inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        return text_features[0].detach().cpu().tolist()


_embedder: ClipEmbedder | None = None


def get_embedder() -> ClipEmbedder:
    """Return a singleton CLIP embedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = ClipEmbedder()
    return _embedder
