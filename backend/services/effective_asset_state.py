"""
Shared effective asset state logic.
Applies query-time override semantics consistently across services.
"""

from __future__ import annotations

import json

from sqlalchemy import case, func, select

from backend.models import Asset, AssetMetadata, Override, OverrideType
from backend.schemas.asset import AssetResponse


SPONSOR_THRESHOLD = 0.40


def latest_override_value_expr(override_type: OverrideType):
    """Return latest override value subquery for a given asset and type."""
    return (
        select(Override.value)
        .where(
            Override.asset_id == Asset.id,
            Override.type == override_type,
        )
        .order_by(Override.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )


def effective_duplicate_hidden_expr():
    """Return duplicate visibility with override awareness."""
    return func.coalesce(AssetMetadata.duplicate_hidden, False)


def effective_hidden_expr():
    """Return manual hide visibility boolean."""
    override_value = latest_override_value_expr(OverrideType.HIDE)
    return case(
        (override_value == "true", True),
        (override_value == "false", False),
        else_=False,
    )


def effective_pinned_expr():
    """Return pinned boolean for ordering."""
    override_value = latest_override_value_expr(OverrideType.PIN)
    return case(
        (override_value == "true", True),
        (override_value == "false", False),
        else_=False,
    )


def effective_sponsor_visible_expr():
    """Return sponsor visibility boolean with override awareness."""
    override_value = latest_override_value_expr(OverrideType.SPONSOR_VISIBLE_OVERRIDE)
    return case(
        (override_value == "true", True),
        (override_value == "false", False),
        else_=func.coalesce(
            AssetMetadata.sponsor_visible_score >= SPONSOR_THRESHOLD, False
        ),
    )


def effective_low_quality_flag_expr():
    """Return low-quality flag with useful override awareness."""
    override_value = latest_override_value_expr(OverrideType.USEFUL_OVERRIDE)
    return case(
        (override_value == "true", False),
        (override_value == "false", True),
        else_=func.coalesce(AssetMetadata.low_quality_flag, False),
    )


def latest_override_from_asset(
    asset: Asset, override_type: OverrideType
) -> Override | None:
    """Return latest loaded override for an asset."""
    matching = [
        override for override in asset.overrides if override.type == override_type
    ]
    if not matching:
        return None
    matching.sort(key=lambda override: override.created_at, reverse=True)
    return matching[0]


def is_pinned_asset(asset: Asset) -> bool:
    """Return whether an asset is manually pinned."""
    override = latest_override_from_asset(asset, OverrideType.PIN)
    return override is not None and override.value == "true"


def is_hidden_asset(asset: Asset) -> bool:
    """Return whether an asset is manually hidden."""
    override = latest_override_from_asset(asset, OverrideType.HIDE)
    return override is not None and override.value == "true"


def is_effective_low_quality_asset(asset: Asset) -> bool:
    """Return low-quality state with useful override awareness."""
    override = latest_override_from_asset(asset, OverrideType.USEFUL_OVERRIDE)
    if override is not None:
        return override.value == "false"
    metadata = asset.asset_metadata
    return bool(metadata.low_quality_flag) if metadata is not None else False


def asset_response_with_overrides(asset: Asset) -> AssetResponse:
    """Build asset response applying read-time overrides."""
    response_data = AssetResponse.model_validate(asset).model_dump()
    metadata = response_data.get("metadata")
    if metadata is None:
        return AssetResponse.model_validate(asset)

    caption_override = latest_override_from_asset(asset, OverrideType.CAPTION_OVERRIDE)
    if caption_override is not None:
        metadata["caption"] = caption_override.value

    tag_override = latest_override_from_asset(asset, OverrideType.TAG_OVERRIDE)
    if tag_override is not None and tag_override.value:
        try:
            metadata["tags"] = json.loads(tag_override.value)
        except json.JSONDecodeError:
            metadata["tags"] = metadata.get("tags", [])

    sponsor_override = latest_override_from_asset(
        asset, OverrideType.SPONSOR_VISIBLE_OVERRIDE
    )
    if sponsor_override is not None:
        metadata["sponsor_visible_score"] = (
            1.0 if sponsor_override.value == "true" else 0.0
        )

    useful_override = latest_override_from_asset(asset, OverrideType.USEFUL_OVERRIDE)
    if useful_override is not None:
        metadata["low_quality_flag"] = useful_override.value == "false"

    return AssetResponse.model_validate(response_data)
