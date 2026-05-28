from app.schemas.ai import ImageAnalysisResult
from app.services.vision_service import MockVisionProvider


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
