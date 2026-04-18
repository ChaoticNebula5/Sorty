"""
Assistant service layer.
Handles bounded assistant actions for collections and curated retrieval.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import (
    AssistantAction,
    AssistantRun,
    Asset,
    AssetMetadata,
    Collection,
)
from backend.schemas.assistant import (
    AssistantActionRequest,
    AssistantActionResponse,
    AssistantActionResponseData,
    AssistantActionResult,
)


class AssistantService:
    """Business logic for bounded assistant actions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_action(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> AssistantActionResponse | None:
        """Execute a supported assistant action for an event."""
        if payload.action_type == "create_instagram_pack":
            result = await self._create_instagram_pack(event_id, payload)
        elif payload.action_type == "find_sponsor_visible_media":
            result = await self._find_sponsor_visible_media(event_id, payload)
        elif payload.action_type == "show_best_stage_shots":
            result = await self._show_best_stage_shots(event_id, payload)
        elif payload.action_type == "build_collection_from_filters":
            result = await self._build_collection_from_filters(event_id, payload)
        else:
            raise ValueError("Unsupported assistant action")

        run = AssistantRun(
            event_id=event_id,
            action_type=AssistantAction(payload.action_type),
            input=payload.model_dump(),
            output=result,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        return AssistantActionResponse(
            data=AssistantActionResponseData(
                run_id=run.id,
                action_type=payload.action_type,
                result=AssistantActionResult(**result),
            )
        )

    async def _create_instagram_pack(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict:
        """Create a collection of high-quality curated assets."""
        count = payload.params.count or 20
        min_quality = payload.params.min_quality or 75
        categories = payload.params.prefer_categories or ["portrait", "stage"]

        stmt = (
            select(Asset)
            .join(Asset.asset_metadata)
            .options(selectinload(Asset.asset_metadata))
            .where(
                Asset.event_id == event_id,
                AssetMetadata.primary_category.in_(categories),
                AssetMetadata.usefulness_score >= min_quality,
                AssetMetadata.duplicate_hidden.is_(False),
                AssetMetadata.low_quality_flag.is_(False),
            )
            .order_by(AssetMetadata.usefulness_score.desc(), Asset.uploaded_at.desc())
            .limit(count)
        )
        result = await self.db.execute(stmt)
        assets = result.scalars().all()

        collection_name = (
            f"Instagram Pack - {datetime.now(timezone.utc).date().isoformat()}"
        )
        collection = Collection(event_id=event_id, name=collection_name)
        self.db.add(collection)
        await self.db.flush()

        for asset in assets:
            collection.asset_associations.append({"asset_id": asset.id})

        summary = (
            f"Created pack with {len(assets)} high-quality "
            f"{', '.join(categories)} shots, excluding duplicates and low-quality images."
        )

        return {
            "collection_id": collection.id,
            "collection_name": collection.name,
            "asset_count": len(assets),
            "summary": summary,
        }

    async def _find_sponsor_visible_media(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict:
        """Return summary for sponsor-visible media."""
        count = payload.params.count or 20

        stmt = (
            select(Asset.id)
            .join(Asset.asset_metadata)
            .where(
                Asset.event_id == event_id,
                AssetMetadata.sponsor_visible_score >= 0.4,
                AssetMetadata.duplicate_hidden.is_(False),
            )
            .limit(count)
        )
        result = await self.db.execute(stmt)
        asset_ids = [row[0] for row in result.all()]

        return {
            "asset_count": len(asset_ids),
            "summary": f"Found {len(asset_ids)} sponsor-visible assets for review.",
            "extra": {"asset_ids": asset_ids},
        }

    async def _show_best_stage_shots(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict:
        """Return summary for top stage shots."""
        count = payload.params.count or 20

        stmt = (
            select(Asset.id)
            .join(Asset.asset_metadata)
            .where(
                Asset.event_id == event_id,
                AssetMetadata.primary_category == "stage",
                AssetMetadata.duplicate_hidden.is_(False),
                AssetMetadata.low_quality_flag.is_(False),
            )
            .order_by(AssetMetadata.usefulness_score.desc(), Asset.uploaded_at.desc())
            .limit(count)
        )
        result = await self.db.execute(stmt)
        asset_ids = [row[0] for row in result.all()]

        return {
            "asset_count": len(asset_ids),
            "summary": f"Selected {len(asset_ids)} strong stage shots.",
            "extra": {"asset_ids": asset_ids},
        }

    async def _build_collection_from_filters(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict:
        """Create a collection from assistant filter preferences."""
        count = payload.params.count or 20
        min_quality = payload.params.min_quality or 0
        categories = payload.params.prefer_categories

        stmt = (
            select(Asset)
            .join(Asset.asset_metadata)
            .options(selectinload(Asset.asset_metadata))
            .where(
                Asset.event_id == event_id,
                AssetMetadata.usefulness_score >= min_quality,
                AssetMetadata.duplicate_hidden.is_(False),
            )
            .order_by(AssetMetadata.usefulness_score.desc(), Asset.uploaded_at.desc())
            .limit(count)
        )

        if categories:
            stmt = stmt.where(AssetMetadata.primary_category.in_(categories))

        result = await self.db.execute(stmt)
        assets = result.scalars().all()

        collection_name = (
            f"Assistant Collection - {datetime.now(timezone.utc).date().isoformat()}"
        )
        collection = Collection(event_id=event_id, name=collection_name)
        self.db.add(collection)
        await self.db.flush()

        for asset in assets:
            collection.asset_associations.append({"asset_id": asset.id})

        return {
            "collection_id": collection.id,
            "collection_name": collection.name,
            "asset_count": len(assets),
            "summary": f"Built collection with {len(assets)} assets from assistant filters.",
        }
