import uuid
from types import SimpleNamespace

from app.services import search_service


def make_media(**overrides: object) -> SimpleNamespace:
    data = {
        "id": uuid.uuid4(),
        "original_filename": "IMG_001.jpg",
        "ai_analysis": SimpleNamespace(
            caption="Students performing on stage.",
            primary_subject="dance group",
            scene_type="performance",
            event_context="college fest",
            tags=["dance", "stage"],
            suggested_primary_folder="Performances",
            suggested_sub_folder="Dance",
        ),
        "review_decision": None,
        "quality_signal": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_mock_embedding_provider_is_deterministic_and_normalized() -> None:
    provider = search_service.MockEmbeddingProvider(dimension=8)

    first = provider.embed_text("Stage Performance")
    second = provider.embed_text(" stage   performance ")

    assert first == second
    assert len(first) == 8
    assert round(sum(value * value for value in first), 6) == 1


def test_mock_embedding_provider_defaults_to_media_embedding_dimension() -> None:
    provider = search_service.MockEmbeddingProvider()

    assert provider.dimension == search_service.MEDIA_EMBEDDING_DIMENSION


def test_build_indexed_text_prefers_review_metadata() -> None:
    media = make_media(
        review_decision=SimpleNamespace(
            final_primary_folder="Highlights",
            final_sub_folder="Opening Dance",
            final_tags=["featured", "approved"],
            review_reasons=["low_confidence"],
            reviewer_note="Use this in recap.",
        ),
        quality_signal=SimpleNamespace(quality_label="sharp"),
    )

    indexed_text = search_service.build_indexed_text(media)

    assert "Students performing on stage." in indexed_text
    assert "Highlights" in indexed_text
    assert "Opening Dance" in indexed_text
    assert "featured" in indexed_text
    assert "low_confidence" in indexed_text
    assert "sharp" in indexed_text


def test_search_result_score_converts_distance_to_similarity() -> None:
    media = make_media()
    result = search_service.SearchResult(media=media, score=max(0.0, 1.0 - 0.25))

    assert result.score == 0.75
