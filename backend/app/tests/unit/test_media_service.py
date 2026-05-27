import uuid

from app.services.media_service import (
    build_original_object_key,
    build_thumbnail_object_key,
)


def test_build_original_object_key() -> None:
    event_id = uuid.uuid4()
    media_id = uuid.uuid4()

    key = build_original_object_key(event_id, media_id, ".jpg")

    assert key == f"events/{event_id}/originals/{media_id}.jpg"


def test_build_thumbnail_object_key() -> None:
    event_id = uuid.uuid4()
    media_id = uuid.uuid4()

    key = build_thumbnail_object_key(event_id, media_id)

    assert key == f"events/{event_id}/thumbnails/{media_id}.jpg"
