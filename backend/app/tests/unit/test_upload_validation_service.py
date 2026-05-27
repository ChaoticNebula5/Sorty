from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.services.upload_validation_service import (
    UploadValidationError,
    sanitize_filename,
    validate_upload,
)


def make_image_bytes(
    image_format: str = "JPEG",
    size: tuple[int, int] = (40, 20),
) -> bytes:
    image = Image.new("RGB", size, color="red")
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def test_validate_upload_accepts_valid_jpeg() -> None:
    data = make_image_bytes("JPEG", size=(40, 20))
    settings = SimpleNamespace(max_upload_size_mb=10)

    result = validate_upload("photo.jpg", "image/jpeg", data, settings)

    assert result.sanitized_filename == "photo.jpg"
    assert result.file_extension == ".jpg"
    assert result.mime_type == "image/jpeg"
    assert result.size_bytes == len(data)
    assert result.image_width == 40
    assert result.image_height == 20


def test_sanitize_filename_rejects_path_separator() -> None:
    with pytest.raises(UploadValidationError) as exc_info:
        sanitize_filename("../photo.jpg")

    assert exc_info.value.code == "invalid_filename"


@pytest.mark.parametrize("filename", ["folder\\photo.jpg", "", ".", ".."])
def test_sanitize_filename_rejects_invalid_names(filename: str) -> None:
    with pytest.raises(UploadValidationError) as exc_info:
        sanitize_filename(filename)

    assert exc_info.value.code == "invalid_filename"


def test_validate_upload_accepts_uppercase_extension() -> None:
    data = make_image_bytes("JPEG")
    settings = SimpleNamespace(max_upload_size_mb=10)

    result = validate_upload("PHOTO.JPG", "image/jpeg", data, settings)

    assert result.file_extension == ".jpg"


def test_validate_upload_accepts_png() -> None:
    data = make_image_bytes("PNG")
    settings = SimpleNamespace(max_upload_size_mb=10)

    result = validate_upload("photo.png", "image/png", data, settings)

    assert result.file_extension == ".png"
    assert result.mime_type == "image/png"


def test_validate_upload_rejects_unsupported_extension() -> None:
    data = make_image_bytes()
    settings = SimpleNamespace(max_upload_size_mb=10)

    with pytest.raises(UploadValidationError) as exc_info:
        validate_upload("photo.gif", "image/gif", data, settings)

    assert exc_info.value.code == "unsupported_file_type"


def test_validate_upload_rejects_wrong_mime_type() -> None:
    data = make_image_bytes()
    settings = SimpleNamespace(max_upload_size_mb=10)

    with pytest.raises(UploadValidationError) as exc_info:
        validate_upload("photo.jpg", "image/png", data, settings)

    assert exc_info.value.code == "invalid_mime_type"


def test_validate_upload_rejects_extension_content_type_mismatch() -> None:
    data = make_image_bytes("PNG")
    settings = SimpleNamespace(max_upload_size_mb=10)

    with pytest.raises(UploadValidationError) as exc_info:
        validate_upload("photo.jpg", "image/jpeg", data, settings)

    assert exc_info.value.code == "invalid_image_format"


def test_validate_upload_rejects_empty_file() -> None:
    settings = SimpleNamespace(max_upload_size_mb=10)

    with pytest.raises(UploadValidationError) as exc_info:
        validate_upload("photo.jpg", "image/jpeg", b"", settings)

    assert exc_info.value.code == "empty_file"


def test_validate_upload_rejects_large_file_before_image_open() -> None:
    settings = SimpleNamespace(max_upload_size_mb=0)

    with pytest.raises(UploadValidationError) as exc_info:
        validate_upload("photo.jpg", "image/jpeg", b"not-image", settings)

    assert exc_info.value.code == "file_too_large"


def test_validate_upload_rejects_unreadable_image() -> None:
    settings = SimpleNamespace(max_upload_size_mb=10)

    with pytest.raises(UploadValidationError) as exc_info:
        validate_upload("photo.jpg", "image/jpeg", b"not-image", settings)

    assert exc_info.value.code == "invalid_image"
