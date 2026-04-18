"""
Event-level duplicate clustering worker task.
Builds duplicate clusters from CLIP embedding similarity.
"""

import asyncio
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal
from backend.models import (
    Asset,
    AssetMetadata,
    DuplicateCluster,
    DuplicateClusterMember,
)


SIMILARITY_THRESHOLD = 0.90


def run(event_id: str) -> None:
    """RQ entrypoint for clustering an event."""
    asyncio.run(_run(UUID(event_id)))


async def _run(event_id: UUID) -> None:
    """Cluster assets for an event using embedding cosine similarity."""
    async with AsyncSessionLocal() as db:
        assets = await _load_assets_with_embeddings(db, event_id)
        if len(assets) < 2:
            return

        adjacency = _build_adjacency(assets)
        components = _connected_components(adjacency)

        await _replace_clusters(db, event_id, assets, components)
        await db.commit()


async def _load_assets_with_embeddings(
    db: AsyncSession, event_id: UUID
) -> list[tuple[Asset, AssetMetadata]]:
    """Load assets for an event that have embeddings."""
    stmt = (
        select(Asset, AssetMetadata)
        .join(Asset.asset_metadata)
        .where(
            Asset.event_id == event_id,
            AssetMetadata.embedding_vector.is_not(None),
        )
    )
    result = await db.execute(stmt)
    return result.all()


def _build_adjacency(
    assets: list[tuple[Asset, AssetMetadata]],
) -> dict[UUID, set[UUID]]:
    """Build graph adjacency based on cosine similarity threshold."""
    adjacency: dict[UUID, set[UUID]] = defaultdict(set)

    for i, (asset_a, metadata_a) in enumerate(assets):
        vector_a = metadata_a.embedding_vector
        if vector_a is None:
            continue

        for asset_b, metadata_b in assets[i + 1 :]:
            vector_b = metadata_b.embedding_vector
            if vector_b is None:
                continue

            similarity = _cosine_similarity(vector_a, vector_b)
            if similarity >= SIMILARITY_THRESHOLD:
                adjacency[asset_a.id].add(asset_b.id)
                adjacency[asset_b.id].add(asset_a.id)

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

    existing_stmt = select(DuplicateCluster).where(
        DuplicateCluster.event_id == event_id
    )
    existing_result = await db.execute(existing_stmt)
    existing_clusters = existing_result.scalars().all()

    for cluster in existing_clusters:
        await db.delete(cluster)

    for component in components:
        ranked_assets = sorted(
            (asset_map[asset_id] for asset_id in component),
            key=lambda item: (
                item[1].usefulness_score or 0,
                item[0].uploaded_at,
            ),
            reverse=True,
        )

        representative_asset = ranked_assets[0][0]

        cluster = DuplicateCluster(
            event_id=event_id,
            representative_asset_id=representative_asset.id,
        )
        db.add(cluster)
        await db.flush()

        for rank, (asset, metadata) in enumerate(ranked_assets, start=1):
            similarity = (
                1.0
                if asset.id == representative_asset.id
                else _cosine_similarity(
                    metadata.embedding_vector,
                    ranked_assets[0][1].embedding_vector,
                )
            )

            member = DuplicateClusterMember(
                cluster_id=cluster.id,
                asset_id=asset.id,
                similarity_score=similarity,
                rank=rank,
            )
            db.add(member)

            metadata.duplicate_hidden = rank > 1


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """Compute cosine similarity between two normalized vectors."""
    return float(sum(a * b for a, b in zip(vector_a, vector_b)))
