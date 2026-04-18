"""
Event service layer.
Handles event CRUD operations and event statistics.
"""

from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Asset, DuplicateCluster, Event, ProcessingStatus
from backend.schemas.event import (
    EventCreate,
    EventListItem,
    EventResponse,
    EventStats,
    EventUpdate,
    EventWithStats,
)


class EventService:
    """Business logic for event operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, payload: EventCreate) -> EventResponse:
        """Create a new event."""
        event = Event(name=payload.name)
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return EventResponse.model_validate(event)

    async def list_events(self) -> list[EventListItem]:
        """List events with asset counters."""
        stmt = (
            select(
                Event.id,
                Event.name,
                Event.created_at,
                func.count(Asset.id).label("asset_count"),
                func.count(
                    case((Asset.processing_status == ProcessingStatus.COMPLETED, 1))
                ).label("processed_count"),
            )
            .outerjoin(Asset, Asset.event_id == Event.id)
            .group_by(Event.id, Event.name, Event.created_at)
            .order_by(Event.created_at.desc())
        )

        result = await self.db.execute(stmt)

        return [
            EventListItem(
                id=row.id,
                name=row.name,
                asset_count=row.asset_count,
                processed_count=row.processed_count,
                created_at=row.created_at,
            )
            for row in result.all()
        ]

    async def get_event(self, event_id: UUID) -> EventWithStats | None:
        """Get a single event with statistics."""
        event = await self.db.get(Event, event_id)
        if event is None:
            return None

        stats_stmt = select(
            func.count(Asset.id).label("total_assets"),
            func.count(
                case((Asset.processing_status == ProcessingStatus.COMPLETED, 1))
            ).label("processed"),
            func.count(
                case((Asset.processing_status == ProcessingStatus.FAILED, 1))
            ).label("failed"),
            func.count(
                case((Asset.processing_status == ProcessingStatus.PENDING, 1))
            ).label("pending"),
            func.count(
                case((Asset.processing_status == ProcessingStatus.PROCESSING, 1))
            ).label("processing"),
        ).where(Asset.event_id == event_id)

        cluster_stmt = select(func.count(DuplicateCluster.id)).where(
            DuplicateCluster.event_id == event_id
        )

        low_quality_stmt = (
            select(func.count(Asset.id))
            .join(Asset.asset_metadata)
            .where(
                Asset.event_id == event_id,
                Asset.asset_metadata.has(low_quality_flag=True),
            )
        )

        stats_result = await self.db.execute(stats_stmt)
        cluster_result = await self.db.execute(cluster_stmt)
        low_quality_result = await self.db.execute(low_quality_stmt)

        stats_row = stats_result.one()

        return EventWithStats(
            id=event.id,
            name=event.name,
            created_at=event.created_at,
            updated_at=event.updated_at,
            stats=EventStats(
                total_assets=stats_row.total_assets,
                processed=stats_row.processed,
                failed=stats_row.failed,
                pending=stats_row.pending,
                processing=stats_row.processing,
                duplicate_clusters=cluster_result.scalar_one(),
                low_quality_count=low_quality_result.scalar_one(),
            ),
        )

    async def update_event(
        self, event_id: UUID, payload: EventUpdate
    ) -> EventResponse | None:
        """Rename an existing event."""
        event = await self.db.get(Event, event_id)
        if event is None:
            return None

        event.name = payload.name
        await self.db.commit()
        await self.db.refresh(event)
        return EventResponse.model_validate(event)
