"""
Retrieval service layer.
Handles asset listing, smart views, and PRD-aligned hybrid search.
"""

from uuid import UUID

from sqlalchemy import Float, bindparam, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.ai.embedder import get_embedder
from backend.models import Asset, AssetMetadata
from backend.services.effective_asset_state import (
    asset_response_with_overrides,
    effective_duplicate_hidden_expr,
    effective_hidden_expr,
    effective_low_quality_flag_expr,
    effective_pinned_expr,
    effective_sponsor_visible_expr,
    is_pinned_asset,
)
from backend.schemas.asset import AssetListData, AssetListResponse, AssetResponse
from backend.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResponseData,
    SearchResultItem,
    SearchScore,
)

VECTOR_CANDIDATE_LIMIT = 200


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
        effective_duplicate_hidden = effective_duplicate_hidden_expr()
        effective_low_quality_flag = effective_low_quality_flag_expr()
        effective_sponsor_visible = effective_sponsor_visible_expr()
        effective_hidden = effective_hidden_expr()
        effective_pinned = effective_pinned_expr()

        filters = [Asset.event_id == event_id]
        filters.extend(
            self._build_asset_filters(
                view=view,
                exclude_duplicates=exclude_duplicates,
                exclude_low_quality=exclude_low_quality,
                effective_duplicate_hidden=effective_duplicate_hidden,
                effective_low_quality_flag=effective_low_quality_flag,
                effective_sponsor_visible=effective_sponsor_visible,
                effective_hidden=effective_hidden,
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
            .order_by(
                desc(effective_pinned), *self._build_asset_sort(sort=sort, order=order)
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        assets = result.scalars().all()

        return AssetListResponse(
            data=AssetListData(
                total_count=total_count,
                limit=limit,
                offset=offset,
                assets=[asset_response_with_overrides(asset) for asset in assets],
            )
        )

    async def search_assets(
        self,
        event_id: UUID,
        payload: SearchRequest,
    ) -> SearchResponse:
        """Perform PRD-aligned hybrid search using CLIP, pgvector, and FTS."""
        query_text = payload.query.strip()
        query_vector = get_embedder().embed_text(query_text)
        query_categories = set(payload.filters.categories or [])
        query_categories.update(self._infer_query_categories(query_text))

        effective_duplicate_hidden = effective_duplicate_hidden_expr()
        effective_low_quality_flag = effective_low_quality_flag_expr()
        effective_hidden = effective_hidden_expr()

        base_filters = [Asset.event_id == event_id]
        base_filters.extend(
            self._build_search_filters(
                payload=payload,
                effective_duplicate_hidden=effective_duplicate_hidden,
                effective_low_quality_flag=effective_low_quality_flag,
                effective_hidden=effective_hidden,
            )
        )

        # Bind with the column's Vector type explicitly to avoid malformed asyncpg binds.
        query_vector_param = bindparam(
            "query_vector",
            value=query_vector,
            type_=AssetMetadata.embedding_vector.type,
        )
        cosine_distance = AssetMetadata.embedding_vector.cosine_distance(
            query_vector_param
        )
        semantic_similarity_expr = (1.0 - cosine_distance).cast(Float)

        vector_stmt = (
            select(
                Asset.id.label("asset_id"),
                func.coalesce(semantic_similarity_expr, 0.0).label(
                    "semantic_similarity"
                ),
            )
            .join(Asset.asset_metadata)
            .where(*base_filters, AssetMetadata.embedding_vector.is_not(None))
            .order_by(cosine_distance)
            .limit(VECTOR_CANDIDATE_LIMIT)
        )
        vector_result = await self.db.execute(vector_stmt)
        vector_rows = vector_result.all()

        candidate_map: dict[UUID, dict[str, float]] = {
            row.asset_id: {
                "semantic_similarity": max(
                    0.0, min(1.0, float(row.semantic_similarity))
                ),
                "keyword_match": 0.0,
            }
            for row in vector_rows
        }

        candidate_ids = list(candidate_map)
        if not candidate_ids:
            return SearchResponse(
                data=SearchResponseData(
                    total_count=0,
                    limit=payload.limit,
                    offset=payload.offset,
                    results=[],
                )
            )

        ts_query = func.plainto_tsquery("english", query_text)
        keyword_stmt = select(
            AssetMetadata.asset_id.label("asset_id"),
            func.ts_rank(AssetMetadata.fts_vector, ts_query).label("keyword_match"),
        ).where(
            AssetMetadata.asset_id.in_(candidate_ids),
            AssetMetadata.fts_vector.op("@@")(ts_query),
        )
        keyword_result = await self.db.execute(keyword_stmt)
        for row in keyword_result.all():
            candidate_map[row.asset_id]["keyword_match"] = max(
                0.0, min(1.0, float(row.keyword_match or 0.0))
            )

        asset_stmt = (
            select(Asset)
            .options(selectinload(Asset.asset_metadata))
            .where(Asset.id.in_(candidate_ids))
        )
        asset_result = await self.db.execute(asset_stmt)
        assets = asset_result.scalars().all()

        ranked_results: list[tuple[Asset, SearchScore]] = []
        for asset in assets:
            metadata = asset.asset_metadata
            if metadata is None:
                continue

            candidate = candidate_map.get(asset.id)
            if candidate is None:
                continue

            usefulness_score_normalized = max(
                0.0, min(1.0, float((metadata.usefulness_score or 0) / 100.0))
            )
            category_match = (
                1.0
                if query_categories and metadata.primary_category in query_categories
                else 0.0
            )
            total = (
                0.4 * candidate["semantic_similarity"]
                + 0.3 * candidate["keyword_match"]
                + 0.2 * usefulness_score_normalized
                + 0.1 * category_match
            )

            ranked_results.append(
                (
                    asset,
                    SearchScore(
                        total=total,
                        semantic_similarity=candidate["semantic_similarity"],
                        keyword_match=candidate["keyword_match"],
                        usefulness_score_normalized=usefulness_score_normalized,
                        category_match=category_match,
                    ),
                )
            )

        if payload.filters.categories:
            ranked_results = [
                item
                for item in ranked_results
                if item[0].asset_metadata is not None
                and item[0].asset_metadata.primary_category
                in payload.filters.categories
            ]

        if payload.sort == "date":
            ranked_results.sort(
                key=lambda item: (
                    is_pinned_asset(item[0]),
                    item[0].uploaded_at,
                ),
                reverse=True,
            )
        elif payload.sort == "quality":
            ranked_results.sort(
                key=lambda item: (
                    is_pinned_asset(item[0]),
                    item[0].asset_metadata.usefulness_score
                    if item[0].asset_metadata is not None
                    else 0,
                ),
                reverse=True,
            )
        else:
            ranked_results.sort(
                key=lambda item: (
                    is_pinned_asset(item[0]),
                    item[1].total,
                    item[0].uploaded_at,
                ),
                reverse=True,
            )

        total_count = len(ranked_results)
        paginated_results = ranked_results[
            payload.offset : payload.offset + payload.limit
        ]

        return SearchResponse(
            data=SearchResponseData(
                total_count=total_count,
                limit=payload.limit,
                offset=payload.offset,
                results=[
                    SearchResultItem(
                        asset=asset_response_with_overrides(asset),
                        score=score,
                    )
                    for asset, score in paginated_results
                ],
            )
        )

    def _build_asset_filters(
        self,
        view: str,
        exclude_duplicates: bool,
        exclude_low_quality: bool,
        effective_duplicate_hidden,
        effective_low_quality_flag,
        effective_sponsor_visible,
        effective_hidden,
    ) -> list:
        """Build smart view and exclusion filters."""
        filters: list = []

        filters.append(effective_hidden.is_(False))

        if exclude_duplicates and view != "duplicates":
            filters.append(effective_duplicate_hidden.is_(False))

        if exclude_low_quality and view != "low_quality":
            filters.append(effective_low_quality_flag.is_(False))

        if view in {"stage", "crowd", "team", "performance", "portrait"}:
            filters.append(AssetMetadata.primary_category == view)
        elif view == "sponsor":
            filters.append(effective_sponsor_visible.is_(True))
        elif view == "duplicates":
            filters.append(effective_duplicate_hidden.is_(True))
        elif view == "low_quality":
            filters.append(effective_low_quality_flag.is_(True))

        return filters

    def _build_asset_sort(self, sort: str, order: str) -> tuple:
        """Build ordering clause for asset lists."""
        descending = order == "desc"

        if sort == "quality":
            column = AssetMetadata.usefulness_score
        else:
            column = Asset.uploaded_at

        primary_order = desc(column) if descending else column.asc()
        secondary_order = (
            desc(Asset.uploaded_at) if descending else Asset.uploaded_at.asc()
        )
        return (primary_order, secondary_order)

    def _build_search_filters(
        self,
        payload: SearchRequest,
        effective_duplicate_hidden,
        effective_low_quality_flag,
        effective_hidden,
    ) -> list:
        """Build deterministic SQL filters used before hybrid scoring."""
        filters: list = []

        filters.append(effective_hidden.is_(False))

        if payload.filters.min_quality > 0:
            filters.append(
                AssetMetadata.usefulness_score >= payload.filters.min_quality
            )

        if payload.filters.exclude_duplicates:
            filters.append(effective_duplicate_hidden.is_(False))

        if payload.filters.exclude_low_quality:
            filters.append(effective_low_quality_flag.is_(False))

        return filters

    def _infer_query_categories(self, query: str) -> set[str]:
        """Infer likely categories from the free-text search query."""
        query_lower = query.lower()
        inferred: set[str] = set()
        category_keywords = {
            "stage": {"stage", "concert", "band", "dj"},
            "crowd": {"crowd", "audience", "fans"},
            "team": {"team", "staff", "crew", "group"},
            "performance": {"performance", "performer", "show", "dance"},
            "portrait": {"portrait", "close-up", "headshot", "person"},
        }

        for category, keywords in category_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                inferred.add(category)

        return inferred
