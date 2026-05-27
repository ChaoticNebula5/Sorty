from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning

from app.core.config import Settings, get_settings


class ThumbnailError(ValueError):
    pass


def generate_thumbnail_jpeg(
    data: bytes,
    settings: Settings | None = None,
) -> bytes:
    resolved_settings = settings or get_settings()
    if resolved_settings.thumbnail_size <= 0:
        raise ThumbnailError("Thumbnail size must be positive.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)

            with Image.open(BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail(
                    (resolved_settings.thumbnail_size, resolved_settings.thumbnail_size)
                )

                if image.mode != "RGB":
                    image = image.convert("RGB")

                output = BytesIO()
                image.save(output, format="JPEG", quality=85, optimize=True)
                return output.getvalue()
    except (DecompressionBombError, DecompressionBombWarning) as exc:
        raise ThumbnailError("Cannot generate thumbnail for oversized image.") from exc
    except UnidentifiedImageError as exc:
        raise ThumbnailError("Cannot generate thumbnail for unreadable image.") from exc
    except OSError as exc:
        raise ThumbnailError("Cannot generate thumbnail for unreadable image.") from exc
