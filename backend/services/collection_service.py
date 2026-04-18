"""
Collection service layer.
Handles collection creation, listing, and asset membership management.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Collection, CollectionAsset
from backend.schemas.collection import (
    AddCollectionAssetsRequest,
    AddCollectionAssetsResponse,
    AddCollectionAssetsResponseData,
    CollectionCreate,
    CollectionListItem,
    CollectionListResponse,
    CollectionResponse,
    RemoveCollectionAssetResponse,
    RemoveCollectionAssetResponseData,
)


class CollectionService:
    """Business logic for collection operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_collection(
        self, event_id: UUID, payload: CollectionCreate
    ) -> CollectionResponse:
        """Create a new collection for an event."""
        collection = Collection(event_id=event_id, name=payload.name)
        self.db.add(collection)
        await self.db.commit()
        await self.db.refresh(collection)

        return CollectionResponse(
            id=collection.id,
            event_id=collection.event_id,
            name=collection.name,
            asset_count=0,
            created_at=collection.created_at,
        )

    async def list_collections(self, event_id: UUID) -> CollectionListResponse:
        """List collections for an event with asset counts."""
        stmt = (
            select(
                Collection.id,
                Collection.name,
                Collection.created_at,
                func.count(CollectionAsset.asset_id).label("asset_count"),
            )
            .outerjoin(
                CollectionAsset,
                CollectionAsset.collection_id == Collection.id,
            )
            .where(Collection.event_id == event_id)
            .group_by(Collection.id, Collection.name, Collection.created_at)
            .order_by(Collection.created_at.desc())
        )

        result = await self.db.execute(stmt)

        return CollectionListResponse(
            data=[
                CollectionListItem(
                    id=row.id,
                    name=row.name,
                    asset_count=row.asset_count,
                    created_at=row.created_at,
                )
                for row in result.all()
            ]
        )

    async def add_assets(
        self, collection_id: UUID, payload: AddCollectionAssetsRequest
    ) -> AddCollectionAssetsResponse:
        """Add assets to a collection, skipping existing links."""
        stmt = (
            insert(CollectionAsset)
            .values(
                [
                    {"collection_id": collection_id, "asset_id": asset_id}
                    for asset_id in payload.asset_ids
                ]
            )
            .on_conflict_do_nothing(index_elements=["collection_id", "asset_id"])
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        added = result.rowcount or 0
        return AddCollectionAssetsResponse(
            data=AddCollectionAssetsResponseData(
                added=added,
                already_present=len(payload.asset_ids) - added,
            )
        )

    async def remove_asset(
        self, collection_id: UUID, asset_id: UUID
    ) -> RemoveCollectionAssetResponse:
        """Remove a single asset from a collection."""
        stmt = select(CollectionAsset).where(
            CollectionAsset.collection_id == collection_id,
            CollectionAsset.asset_id == asset_id,
        )
        result = await self.db.execute(stmt)
        collection_asset = result.scalar_one_or_none()

        if collection_asset is not None:
            await self.db.delete(collection_asset)
            await self.db.commit()
            removed = True
        else:
            removed = False

        return RemoveCollectionAssetResponse(
            data=RemoveCollectionAssetResponseData(removed=removed)
        )
