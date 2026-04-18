"""
Image quality scoring utilities for Sorty.
Provides blur, brightness, and usefulness heuristics.
"""

from io import BytesIO

import numpy as np
from PIL import Image
from scipy.ndimage import laplace


class QualityScorer:
    """Computes simple image quality heuristics."""

    def score_image_bytes(self, image_bytes: bytes) -> dict[str, float | int | bool]:
        """Return quality-related scores for an image."""
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        grayscale = np.asarray(image.convert("L"), dtype=np.float32)

        blur_score = float(np.var(laplace(grayscale)))
        brightness_score = float(np.mean(grayscale) / 255.0)

        usefulness_score = self._compute_usefulness_score(
            blur_score=blur_score,
            brightness_score=brightness_score,
        )
        low_quality_flag = usefulness_score < 40

        return {
            "blur_score": blur_score,
            "brightness_score": brightness_score,
            "usefulness_score": usefulness_score,
            "low_quality_flag": low_quality_flag,
        }

    @staticmethod
    def _compute_usefulness_score(
        blur_score: float,
        brightness_score: float,
    ) -> int:
        """Combine heuristics into a 0-100 usefulness score."""
        blur_component = min(blur_score / 1000.0, 1.0) * 60.0

        brightness_distance = abs(brightness_score - 0.5)
        brightness_component = max(0.0, 1.0 - (brightness_distance * 2.0)) * 40.0

        return int(round(blur_component + brightness_component))


_quality_scorer: QualityScorer | None = None


def get_quality_scorer() -> QualityScorer:
    """Return a singleton quality scorer instance."""
    global _quality_scorer
    if _quality_scorer is None:
        _quality_scorer = QualityScorer()
    return _quality_scorer
