import uuid

from app.services.event_service import slugify


def test_slugify_normalizes_event_name() -> None:
    assert slugify("Cultural Fest 2026!") == "cultural-fest-2026"


def test_slugify_uses_fallback_for_empty_result() -> None:
    assert slugify("!!!") == "event"


class FakeSlugDb:
    def __init__(self, results: list[uuid.UUID | None]) -> None:
        self.results = results
        self.calls = 0

    def scalar(self, statement):
        self.calls += 1
        return self.results.pop(0)


def test_make_unique_public_slug_auto_resolves_collision() -> None:
    from app.services.event_service import make_unique_public_slug

    db = FakeSlugDb([uuid.uuid4(), None])

    assert make_unique_public_slug(db, "Launch Party") == "launch-party-2"
    assert db.calls == 2
