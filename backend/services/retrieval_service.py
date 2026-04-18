"""
Retrieval service layer.
Handles asset listing, smart views, and hybrid search.
"""

from uuid import UUID

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Asset, AssetMetadata
from backend.schemas.asset import AssetListData, AssetListResponse, AssetResponse
from backend.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResponseData,
    SearchResultItem,
    SearchScore,
)


class RetrievalService:
    """Business logic for asset retrieval and search."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_assets(
        self,
        event_id: UUID,
        view: str = "all",
        limit: int = 50,
        offset: int = 0,
        sort: str = "date",
        order: str = "desc",
        exclude_duplicates: bool = True,
        exclude_low_quality: bool = False,
    ) -> AssetListResponse:
        """List event assets with smart view filters."""
        filters = [Asset.event_id == event_id]
        filters.extend(
            self._build_asset_filters(
                view=view,
                exclude_duplicates=exclude_duplicates,
                exclude_low_quality=exclude_low_quality,
            )
        )

        total_stmt = (
            select(func.count(Asset.id))
            .outerjoin(AssetMetadata, AssetMetadata.asset_id == Asset.id)
            .where(*filters)
        )
        total_result = await self.db.execute(total_stmt)
        total_count = total_result.scalar_one()

        stmt = (
            select(Asset)
            .outerjoin(AssetMetadata, AssetMetadata.asset_id == Asset.id)
            .options(selectinload(Asset.asset_metadata))
            .where(*filters)
            .offset(offset)
            .limit(limit)
        )

        stmt = stmt.order_by(*self._build_asset_sort(sort=sort, order=order))

        result = await self.db.execute(stmt)
        assets = result.scalars().all()

        return AssetListResponse(
            data=AssetListData(
                total_count=total_count,
                limit=limit,
                offset=offset,
                assets=[AssetResponse.model_validate(asset) for asset in assets],
            )
        )

    async def search_assets(
        self,
        event_id: UUID,
        payload: SearchRequest,
    ) -> SearchResponse:
        """Perform simplified hybrid search using metadata fields."""
        filters = [Asset.event_id == event_id]
        metadata_filters = []

        if payload.filters.categories:
            metadata_filters.append(
                AssetMetadata.primary_category.in_(payload.filters.categories)
            )

        if payload.filters.min_quality > 0:
            metadata_filters.append(
                AssetMetadata.usefulness_score >= payload.filters.min_quality
            )

        if payload.filters.exclude_duplicates:
            metadata_filters.append(
                or_(
                    AssetMetadata.duplicate_hidden.is_(False),
                    AssetMetadata.duplicate_hidden.is_(None),
                )
            )

        if payload.filters.exclude_low_quality:
            metadata_filters.append(
                or_(
                    AssetMetadata.low_quality_flag.is_(False),
                    AssetMetadata.low_quality_flag.is_(None),
                )
            )

        query_text = payload.query.strip()
        ilike_query = f"%{query_text}%"

        semantic_similarity = case(
            (
                AssetMetadata.caption.ilike(ilike_query),
                0.9,
            ),
            else_=0.0,
        )

        keyword_match = case(
            (
                or_(
                    AssetMetadata.caption.ilike(ilike_query),
                    AssetMetadata.tags_json.cast(
                        type_=AssetMetadata.tags_json.type
                    ).is_not(None),
                ),
                0.8,
            ),
            else_=0.0,
        )

        usefulness_score_normalized = func.coalesce(
            AssetMetadata.usefulness_score / 100.0,
            0.0,
        )

        category_match = case(
            (
                and_(
                    payload.filters.categories is not None,
                    AssetMetadata.primary_category.in_(
                        payload.filters.categories or []
                    ),
                ),
                1.0,
            ),
            else_=0.0,
        )

        total_score = (
            0.4 * semantic_similarity
            + 0.3 * keyword_match
            + 0.2 * usefulness_score_normalized
            + 0.1 * category_match
        )

        stmt = (
            select(
                Asset,
                func.coalesce(total_score, 0.0).label("total_score"),
                func.coalesce(semantic_similarity, 0.0).label("semantic_similarity"),
                func.coalesce(keyword_match, 0.0).label("keyword_match"),
                func.coalesce(usefulness_score_normalized, 0.0).label(
                    "usefulness_score_normalized"
                ),
                func.coalesce(category_match, 0.0).label("category_match"),
            )
            .outerjoin(AssetMetadata, AssetMetadata.asset_id == Asset.id)
            .options(selectinload(Asset.asset_metadata))
            .where(*filters, *metadata_filters)
        )

        if query_text:
            stmt = stmt.where(
                or_(
                    Asset.filename.ilike(ilike_query),
                    AssetMetadata.caption.ilike(ilike_query),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar_one()

        if payload.sort == "date":
            stmt = stmt.order_by(desc(Asset.uploaded_at))
        elif payload.sort == "quality":
            stmt = stmt.order_by(desc(AssetMetadata.usefulness_score))
        else:
            stmt = stmt.order_by(desc(total_score), desc(Asset.uploaded_at))

        stmt = stmt.offset(payload.offset).limit(payload.limit)

        result = await self.db.execute(stmt)
        rows = result.all()

        return SearchResponse(
            data=SearchResponseData(
                total_count=total_count,
                limit=payload.limit,
                offset=payload.offset,
                results=[
                    SearchResultItem(
                        asset=AssetResponse.model_validate(row.Asset),
                        score=SearchScore(
                            total=float(row.total_score or 0.0),
                            semantic_similarity=float(row.semantic_similarity or 0.0),
                            keyword_match=float(row.keyword_match or 0.0),
                            usefulness_score_normalized=float(
                                row.usefulness_score_normalized or 0.0
                            ),
                            category_match=float(row.category_match or 0.0),
                        ),
                    )
                    for row in rows
                ],
            )
        )

    def _build_asset_filters(
        self,
        view: str,
        exclude_duplicates: bool,
        exclude_low_quality: bool,
    ) -> list:
        """Build smart view and exclusion filters."""
        filters: list = []

        if exclude_duplicates and view != "duplicates":
            filters.append(
                or_(
                    AssetMetadata.duplicate_hidden.is_(False),
                    AssetMetadata.duplicate_hidden.is_(None),
                )
            )

        if exclude_low_quality and view != "low_quality":
            filters.append(
                or_(
                    AssetMetadata.low_quality_flag.is_(False),
                    AssetMetadata.low_quality_flag.is_(None),
                )
            )

        if view in {"stage", "crowd", "team", "performance", "portrait"}:
            filters.append(AssetMetadata.primary_category == view)
        elif view == "sponsor":
            filters.append(AssetMetadata.sponsor_visible_score >= 0.4)
        elif view == "duplicates":
            filters.append(AssetMetadata.duplicate_hidden.is_(True))
        elif view == "low_quality":
            filters.append(AssetMetadata.low_quality_flag.is_(True))

        return filters

    def _build_asset_sort(self, sort: str, order: str) -> tuple:
        """Build ordering clause for asset lists."""
        descending = order == "desc"

        if sort == "quality":
            column = AssetMetadata.usefulness_score
        else:
            column = Asset.uploaded_at

        direction = desc if descending else lambda value: value.asc()
        return (direction(column), desc(Asset.uploaded_at))
