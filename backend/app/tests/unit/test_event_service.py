from app.services.event_service import slugify


def test_slugify_normalizes_event_name() -> None:
    assert slugify("Cultural Fest 2026!") == "cultural-fest-2026"


def test_slugify_uses_fallback_for_empty_result() -> None:
    assert slugify("!!!") == "event"
