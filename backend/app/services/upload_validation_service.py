from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
import warnings

from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class UploadValidationResult:
    sanitized_filename: str
    file_extension: str
    mime_type: str
    size_bytes: int
    image_width: int
    image_height: int


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_EXTENSION_TO_IMAGE_FORMAT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}


def sanitize_filename(filename: str) -> str:
    name = PurePath(filename).name.strip()

    if not name or name in {".", ".."}:
        raise UploadValidationError(
            "invalid_filename",
            "Uploaded file must have a valid filename.",
        )

    if "/" in filename or "\\" in filename:
        raise UploadValidationError(
            "invalid_filename",
            "Uploaded filename must not contain path separators.",
        )

    return name


def get_file_extension(filename: str) -> str:
    suffix = PurePath(filename).suffix.lower()

    if suffix not in _EXTENSION_TO_MIME:
        raise UploadValidationError(
            "unsupported_file_type",
            "Only jpg, jpeg, png, and webp files are supported.",
        )

    return suffix


def validate_upload(
    filename: str,
    content_type: str | None,
    data: bytes,
    settings: Settings | None = None,
) -> UploadValidationResult:
    resolved_settings = settings or get_settings()
    sanitized_filename = sanitize_filename(filename)
    extension = get_file_extension(sanitized_filename)

    expected_mime = _EXTENSION_TO_MIME[extension]
    if content_type != expected_mime:
        raise UploadValidationError(
            "invalid_mime_type",
            f"Expected MIME type {expected_mime}.",
        )

    size_bytes = len(data)
    if size_bytes <= 0:
        raise UploadValidationError(
            "empty_file",
            "Uploaded file must not be empty.",
        )

    max_size_bytes = resolved_settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_size_bytes:
        raise UploadValidationError(
            "file_too_large",
            f"Uploaded file exceeds {resolved_settings.max_upload_size_mb} MB.",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)

            with Image.open(BytesIO(data)) as image:
                image.verify()

            with Image.open(BytesIO(data)) as image:
                if image.format != _EXTENSION_TO_IMAGE_FORMAT[extension]:
                    raise UploadValidationError(
                        "invalid_image_format",
                        "Image content does not match the file extension.",
                    )
                width, height = image.size
    except (DecompressionBombError, DecompressionBombWarning) as exc:
        raise UploadValidationError(
            "image_too_large",
            "Uploaded image dimensions are too large.",
        ) from exc
    except UnidentifiedImageError as exc:
        raise UploadValidationError(
            "invalid_image",
            "Uploaded file is not a readable image.",
        ) from exc
    except OSError as exc:
        raise UploadValidationError(
            "invalid_image",
            "Uploaded file is not a readable image.",
        ) from exc

    return UploadValidationResult(
        sanitized_filename=sanitized_filename,
        file_extension=extension,
        mime_type=expected_mime,
        size_bytes=size_bytes,
        image_width=width,
        image_height=height,
    )
