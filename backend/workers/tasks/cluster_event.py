"""
Event-level duplicate clustering worker task.
Builds duplicate clusters from CLIP embedding similarity.
"""

import asyncio
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal, close_db
from backend.models import (
    Asset,
    AssetMetadata,
    DuplicateCluster,
    DuplicateClusterMember,
    ProcessingStatus,
)
from backend.workers.queues import get_redis_connection


SIMILARITY_THRESHOLD = 0.90


def run(event_id: str, lock_token: str) -> None:
    """RQ entrypoint for clustering an event."""
    asyncio.run(_run_with_cleanup(UUID(event_id), lock_token))


async def _run_with_cleanup(event_id: UUID, lock_token: str) -> None:
    """Run task and dispose DB connections bound to the event loop."""
    try:
        await _run(event_id, lock_token)
    finally:
        await close_db()


async def _run(event_id: UUID, lock_token: str) -> None:
    """Cluster assets for an event using pgvector neighbor search."""
    redis_connection = get_redis_connection()
    lock_key = f"clustering_lock:{event_id}"

    try:
        async with AsyncSessionLocal() as db:
            assets = await _load_assets_with_embeddings(db, event_id)
            await _reset_duplicate_hidden_flags(db, event_id)

            if len(assets) < 2:
                await _delete_existing_clusters(db, event_id)
                await db.commit()
                return

            adjacency = await _build_adjacency(db, event_id, assets)
            components = _connected_components(adjacency)

            await _replace_clusters(db, event_id, assets, components)
            await db.commit()
    finally:
        redis_connection.eval(
            """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            end
            return 0
            """,
            1,
            lock_key,
            lock_token,
        )


async def _load_assets_with_embeddings(
    db: AsyncSession, event_id: UUID
) -> list[tuple[Asset, AssetMetadata]]:
    """Load completed assets for an event that have embeddings."""
    stmt = (
        select(Asset, AssetMetadata)
        .join(Asset.asset_metadata)
        .where(
            Asset.event_id == event_id,
            Asset.processing_status == ProcessingStatus.COMPLETED,
            AssetMetadata.embedding_vector.is_not(None),
        )
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def _build_adjacency(
    db: AsyncSession,
    event_id: UUID,
    assets: list[tuple[Asset, AssetMetadata]],
) -> dict[UUID, set[UUID]]:
    """Build graph adjacency from pgvector nearest neighbors."""
    adjacency: dict[UUID, set[UUID]] = defaultdict(set)

    for asset, metadata in assets:
        vector = metadata.embedding_vector
        if vector is None:
            continue

        cosine_distance = AssetMetadata.embedding_vector.op("<=>")(vector)
        neighbor_stmt = (
            select(Asset.id.label("asset_id"), cosine_distance.label("distance"))
            .join(Asset.asset_metadata)
            .where(
                Asset.event_id == event_id,
                Asset.processing_status == ProcessingStatus.COMPLETED,
                Asset.id != asset.id,
                AssetMetadata.embedding_vector.is_not(None),
            )
            .order_by(cosine_distance)
            .limit(settings.clustering_max_neighbors)
        )
        neighbor_result = await db.execute(neighbor_stmt)

        for row in neighbor_result.all():
            distance = float(row.distance)
            similarity = 1.0 - distance
            if similarity >= SIMILARITY_THRESHOLD:
                adjacency[asset.id].add(row.asset_id)
                adjacency[row.asset_id].add(asset.id)

    return adjacency


def _connected_components(adjacency: dict[UUID, set[UUID]]) -> list[set[UUID]]:
    """Return connected components from adjacency graph."""
    visited: set[UUID] = set()
    components: list[set[UUID]] = []

    for node in adjacency:
        if node in visited:
            continue

        stack = [node]
        component: set[UUID] = set()

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            component.add(current)
            stack.extend(adjacency[current] - visited)

        if len(component) > 1:
            components.append(component)

    return components


async def _replace_clusters(
    db: AsyncSession,
    event_id: UUID,
    assets: list[tuple[Asset, AssetMetadata]],
    components: list[set[UUID]],
) -> None:
    """Replace existing clusters for event with newly computed ones."""
    asset_map = {asset.id: (asset, metadata) for asset, metadata in assets}
    await _delete_existing_clusters(db, event_id)

    for component in components:
        ranked_assets = sorted(
            (asset_map[asset_id] for asset_id in component),
            key=lambda item: (
                item[1].usefulness_score or 0,
                item[0].uploaded_at,
            ),
            reverse=True,
        )

        representative_asset, representative_metadata = ranked_assets[0]
        representative_vector = representative_metadata.embedding_vector or []

        cluster = DuplicateCluster(
            event_id=event_id,
            representative_asset_id=representative_asset.id,
        )
        db.add(cluster)
        await db.flush()

        for rank, (asset, metadata) in enumerate(ranked_assets, start=1):
            metadata_vector = metadata.embedding_vector or []
            similarity = (
                1.0
                if asset.id == representative_asset.id
                else _cosine_similarity(metadata_vector, representative_vector)
            )

            db.add(
                DuplicateClusterMember(
                    cluster_id=cluster.id,
                    asset_id=asset.id,
                    similarity_score=similarity,
                    rank=rank,
                )
            )
            metadata.duplicate_hidden = rank > 1


async def _delete_existing_clusters(db: AsyncSession, event_id: UUID) -> None:
    """Delete all existing duplicate clusters for an event."""
    existing_stmt = select(DuplicateCluster).where(
        DuplicateCluster.event_id == event_id
    )
    existing_result = await db.execute(existing_stmt)
    existing_clusters = existing_result.scalars().all()

    for cluster in existing_clusters:
        await db.delete(cluster)


async def _reset_duplicate_hidden_flags(db: AsyncSession, event_id: UUID) -> None:
    """Reset duplicate hidden flags before rebuilding clusters."""
    await db.execute(
        update(AssetMetadata)
        .where(
            AssetMetadata.asset_id.in_(
                select(Asset.id).where(Asset.event_id == event_id)
            )
        )
        .values(duplicate_hidden=False)
    )


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """Compute cosine similarity between two normalized vectors."""
    return float(sum(a * b for a, b in zip(vector_a, vector_b)))
