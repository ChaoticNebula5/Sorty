"""
Sponsor visibility helpers for Sorty.
Normalizes sponsor visibility scores returned by the Gemini captioning pass.
"""


class SponsorScorer:
    """Normalizes sponsor visibility score from captioner output."""

    def score_caption_result(self, caption_result: dict) -> dict[str, float]:
        """Return a clamped sponsor visibility score between 0.0 and 1.0."""
        raw_score = caption_result.get("sponsor_visible_score", 0.0)

        try:
            sponsor_visible_score = float(raw_score)
        except (TypeError, ValueError):
            sponsor_visible_score = 0.0

        sponsor_visible_score = max(0.0, min(1.0, sponsor_visible_score))
        return {"sponsor_visible_score": sponsor_visible_score}


_sponsor_scorer: SponsorScorer | None = None


def get_sponsor_scorer() -> SponsorScorer:
    """Return a singleton sponsor scorer instance."""
    global _sponsor_scorer
    if _sponsor_scorer is None:
        _sponsor_scorer = SponsorScorer()
    return _sponsor_scorer
