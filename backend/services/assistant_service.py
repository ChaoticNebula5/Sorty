"""
Assistant service layer.
Handles bounded assistant actions for collections and curated retrieval.
"""

from datetime import datetime, timezone
import uuid
from uuid import UUID

from sqlalchemy import case, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    AssistantAction,
    AssistantRun,
    Asset,
    AssetMetadata,
    Collection,
    CollectionAsset,
    Event,
)
from backend.services.effective_asset_state import (
    effective_duplicate_hidden_expr,
    effective_hidden_expr,
    effective_low_quality_flag_expr,
    effective_pinned_expr,
    effective_sponsor_visible_expr,
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
        result = await self._dispatch_action(event_id, payload)
        if result is None:
            return None

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

    async def _dispatch_action(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict | None:
        """Dispatch assistant action to the correct handler."""
        event_exists = await self._event_exists(event_id)
        if not event_exists:
            return None

        if payload.action_type == "create_instagram_pack":
            return await self._create_instagram_pack(event_id, payload)
        if payload.action_type == "find_sponsor_visible_media":
            return await self._find_sponsor_visible_media(event_id, payload)
        if payload.action_type == "show_best_stage_shots":
            return await self._show_best_stage_shots(event_id, payload)
        if payload.action_type == "build_collection_from_filters":
            return await self._build_collection_from_filters(event_id, payload)

        raise ValueError("Unsupported assistant action")

    async def _event_exists(self, event_id: UUID) -> bool:
        """Check whether an event exists."""
        result = await self.db.execute(select(Event.id).where(Event.id == event_id))
        return result.scalar_one_or_none() is not None

    async def _create_instagram_pack(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict:
        """Create a collection of high-quality curated assets."""
        count = min(payload.params.count or 20, 20)
        min_quality = payload.params.min_quality or 75
        categories = payload.params.prefer_categories or ["portrait", "stage"]

        assets = await self._select_assets(
            event_id=event_id,
            count=count,
            min_quality=min_quality,
            categories=categories,
            sponsor_only=False,
            stage_only=False,
        )

        collection = await self._create_collection_with_assets(
            event_id=event_id,
            name=f"Instagram Pack - {datetime.now(timezone.utc).date().isoformat()}",
            assets=assets,
        )

        return {
            "collection_id": collection.id,
            "collection_name": collection.name,
            "asset_count": len(assets),
            "summary": (
                f"Created pack with {len(assets)} high-quality "
                f"{', '.join(categories)} shots, excluding duplicates and low-quality images."
            ),
        }

    async def _find_sponsor_visible_media(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict:
        """Return summary for sponsor-visible media."""
        count = min(payload.params.count or 20, 100)

        assets = await self._select_assets(
            event_id=event_id,
            count=count,
            min_quality=0,
            categories=None,
            sponsor_only=True,
            stage_only=False,
        )

        return {
            "asset_count": len(assets),
            "summary": f"Found {len(assets)} sponsor-visible assets for review.",
            "extra": {"asset_ids": [asset.id for asset in assets]},
        }

    async def _show_best_stage_shots(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict:
        """Return summary for top stage shots."""
        count = min(payload.params.count or 20, 100)

        assets = await self._select_assets(
            event_id=event_id,
            count=count,
            min_quality=0,
            categories=None,
            sponsor_only=False,
            stage_only=True,
        )

        return {
            "asset_count": len(assets),
            "summary": f"Selected {len(assets)} strong stage shots.",
            "extra": {"asset_ids": [asset.id for asset in assets]},
        }

    async def _build_collection_from_filters(
        self, event_id: UUID, payload: AssistantActionRequest
    ) -> dict:
        """Create a collection from assistant filter preferences."""
        count = min(payload.params.count or 20, 100)
        min_quality = payload.params.min_quality or 0
        categories = payload.params.prefer_categories

        assets = await self._select_assets(
            event_id=event_id,
            count=count,
            min_quality=min_quality,
            categories=categories,
            sponsor_only=False,
            stage_only=False,
        )

        collection = await self._create_collection_with_assets(
            event_id=event_id,
            name=f"Assistant Collection - {datetime.now(timezone.utc).date().isoformat()}",
            assets=assets,
        )

        return {
            "collection_id": collection.id,
            "collection_name": collection.name,
            "asset_count": len(assets),
            "summary": f"Built collection with {len(assets)} assets from assistant filters.",
        }

    async def _select_assets(
        self,
        event_id: UUID,
        count: int,
        min_quality: int,
        categories: list[str] | None,
        sponsor_only: bool,
        stage_only: bool,
    ) -> list[Asset]:
        """Select curated assets for assistant actions."""
        effective_hidden = effective_hidden_expr()
        effective_duplicate_hidden = effective_duplicate_hidden_expr()
        effective_low_quality = effective_low_quality_flag_expr()
        effective_sponsor_visible = effective_sponsor_visible_expr()
        effective_pinned = effective_pinned_expr()

        stmt = (
            select(Asset)
            .join(Asset.asset_metadata)
            .where(
                Asset.event_id == event_id,
                effective_hidden.is_(False),
                effective_duplicate_hidden.is_(False),
                effective_low_quality.is_(False),
                AssetMetadata.usefulness_score >= min_quality,
            )
            .order_by(
                desc(effective_pinned),
                AssetMetadata.usefulness_score.desc(),
                Asset.uploaded_at.desc(),
            )
            .limit(count)
        )

        if categories:
            stmt = stmt.where(AssetMetadata.primary_category.in_(categories))
        if sponsor_only:
            stmt = stmt.where(effective_sponsor_visible.is_(True))
        if stage_only:
            stmt = stmt.where(AssetMetadata.primary_category == "stage")

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _create_collection_with_assets(
        self,
        event_id: UUID,
        name: str,
        assets: list[Asset],
    ) -> Collection:
        """Create a collection and attach asset rows explicitly."""
        collection = Collection(
            event_id=event_id,
            name=name or f"Assistant Collection {uuid.uuid4().hex[:8]}",
        )
        self.db.add(collection)
        await self.db.flush()

        for asset in assets:
            self.db.add(
                CollectionAsset(
                    collection_id=collection.id,
                    asset_id=asset.id,
                )
            )

        await self.db.flush()
        return collection
