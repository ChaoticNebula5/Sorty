import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Event
from app.schemas.events import EventCreate, EventPublicSettingsUpdate

_slug_pattern = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _slug_pattern.sub("-", value.lower()).strip("-")
    return slug or "event"


def make_unique_slug(db: Session, name: str) -> str:
    base_slug = slugify(name)
    slug = base_slug
    counter = 2

    while db.scalar(select(Event.id).where(Event.slug == slug)) is not None:
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def make_unique_public_slug(
    db: Session,
    name: str,
    event_id: uuid.UUID | None = None,
) -> str:
    base_slug = slugify(name)
    public_slug = base_slug
    counter = 2

    while _public_slug_exists(db, public_slug, event_id=event_id):
        public_slug = f"{base_slug}-{counter}"
        counter += 1

    return public_slug


def _public_slug_exists(
    db: Session,
    public_slug: str,
    event_id: uuid.UUID | None = None,
) -> bool:
    statement = select(Event.id).where(Event.public_slug == public_slug)
    if event_id is not None:
        statement = statement.where(Event.id != event_id)
    return db.scalar(statement) is not None


def create_event(db: Session, payload: EventCreate) -> Event:
    event = Event(
        name=payload.name,
        slug=make_unique_slug(db, payload.name),
        event_type=payload.event_type,
        description=payload.description,
        event_date=payload.event_date,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return event


def list_events(db: Session, limit: int = 50, offset: int = 0) -> tuple[list[Event], int]:
    total = db.scalar(
        select(func.count()).select_from(Event).where(Event.archived_at.is_(None))
    ) or 0

    events = list(
        db.scalars(
            select(Event)
            .where(Event.archived_at.is_(None))
            .order_by(Event.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )

    return events, total


def get_event(db: Session, event_id: uuid.UUID) -> Event | None:
    return db.scalar(
        select(Event).where(
            Event.id == event_id,
            Event.archived_at.is_(None),
        )
    )


def update_event_public_settings(
    db: Session,
    event: Event,
    payload: EventPublicSettingsUpdate,
) -> Event:
    if payload.is_public:
        public_slug = payload.public_slug
        if public_slug is None:
            public_slug = make_unique_public_slug(db, event.name, event_id=event.id)
        elif _public_slug_exists(db, public_slug, event_id=event.id):
            raise ValueError("public_slug is already in use.")

        event.is_public = True
        event.public_slug = public_slug
        event.published_at = datetime.now(UTC)
    else:
        event.is_public = False
        event.published_at = None

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("public_slug is already in use.") from exc
    db.refresh(event)

    return event


def get_public_event_by_slug(db: Session, public_slug: str) -> Event | None:
    return db.scalar(
        select(Event).where(
            Event.public_slug == public_slug,
            Event.is_public.is_(True),
            Event.published_at.is_not(None),
            Event.archived_at.is_(None),
        )
    )
