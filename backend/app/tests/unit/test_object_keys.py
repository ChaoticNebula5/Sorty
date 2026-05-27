import pytest

from app.services.object_keys import validate_object_key


def test_validate_object_key_accepts_nested_key() -> None:
    key = validate_object_key("events/event-id/originals/media-id.jpg")

    assert key.parts == ("events", "event-id", "originals", "media-id.jpg")


@pytest.mark.parametrize(
    "object_key",
    [
        "../secret.txt",
        "/absolute/path.jpg",
        "events/../secret.jpg",
        "events//file.jpg",
        "events/./file.jpg",
        "events\\event-id\\file.jpg",
        "",
    ],
)
def test_validate_object_key_rejects_unsafe_keys(object_key: str) -> None:
    with pytest.raises(ValueError):
        validate_object_key(object_key)
