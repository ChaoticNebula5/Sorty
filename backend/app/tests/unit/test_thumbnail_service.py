from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.services.thumbnail_service import ThumbnailError, generate_thumbnail_jpeg


def make_image_bytes(
    image_format: str = "PNG",
    size: tuple[int, int] = (800, 400),
) -> bytes:
    image = Image.new("RGB", size, color="blue")
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def test_generate_thumbnail_jpeg_returns_jpeg_bytes() -> None:
    data = make_image_bytes("PNG")
    settings = SimpleNamespace(thumbnail_size=300)

    thumbnail = generate_thumbnail_jpeg(data, settings)

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
        assert image.width <= 300
        assert image.height <= 300


def test_generate_thumbnail_jpeg_preserves_aspect_ratio() -> None:
    data = make_image_bytes("PNG", size=(800, 400))
    settings = SimpleNamespace(thumbnail_size=200)

    thumbnail = generate_thumbnail_jpeg(data, settings)

    with Image.open(BytesIO(thumbnail)) as image:
        assert image.size == (200, 100)


def test_generate_thumbnail_jpeg_rejects_unreadable_image() -> None:
    settings = SimpleNamespace(thumbnail_size=300)

    with pytest.raises(ThumbnailError):
        generate_thumbnail_jpeg(b"not-image", settings)


def test_generate_thumbnail_jpeg_rejects_non_positive_size() -> None:
    data = make_image_bytes("PNG")
    settings = SimpleNamespace(thumbnail_size=0)

    with pytest.raises(ThumbnailError):
        generate_thumbnail_jpeg(data, settings)
