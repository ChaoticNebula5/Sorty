import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Event
from app.schemas.events import EventCreate

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
