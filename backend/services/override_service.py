"""
Override service layer.
Handles creation of retrieval-time overrides.
"""

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Asset, Override, OverrideType
from backend.schemas.override import OverrideCreate, OverrideResponse


NULL_VALUE_TYPES = {OverrideType.HIDE, OverrideType.PIN}
BOOLEAN_STRING_TYPES = {
    OverrideType.SPONSOR_VISIBLE_OVERRIDE,
    OverrideType.USEFUL_OVERRIDE,
}


class OverrideService:
    """Business logic for creating overrides."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_override(
        self, asset_id: UUID, payload: OverrideCreate
    ) -> OverrideResponse:
        """Create an override for an asset."""
        asset = await self.db.get(Asset, asset_id)
        if asset is None:
            raise ValueError("Asset not found")

        override_type = OverrideType(payload.type)
        validated_value = self._validate_value(override_type, payload.value)

        override = Override(
            asset_id=asset_id,
            type=override_type,
            value=validated_value,
        )
        self.db.add(override)
        await self.db.commit()
        await self.db.refresh(override)
        return OverrideResponse.model_validate(override)

    def _validate_value(
        self, override_type: OverrideType, value: str | None
    ) -> str | None:
        """Validate override payload by type."""
        if override_type in NULL_VALUE_TYPES:
            return None

        if override_type == OverrideType.CAPTION_OVERRIDE:
            if not value or not value.strip():
                raise ValueError("Caption override requires a non-empty value")
            return value.strip()

        if override_type == OverrideType.TAG_OVERRIDE:
            if value is None:
                raise ValueError("Tag override requires a JSON array string")
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Tag override must be a valid JSON array string"
                ) from exc
            if not isinstance(parsed, list) or not all(
                isinstance(item, str) for item in parsed
            ):
                raise ValueError("Tag override must be a JSON array of strings")
            return value

        if override_type in BOOLEAN_STRING_TYPES:
            if value not in {"true", "false"}:
                raise ValueError("Boolean override value must be 'true' or 'false'")
            return value

        return value
