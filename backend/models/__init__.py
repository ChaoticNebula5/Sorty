"""
ORM models package.
Imports all models to make them available to SQLAlchemy and Alembic.
"""

from backend.database import Base

# Import all models (order matters for relationships)
from backend.models.event import Event
from backend.models.asset import Asset, ProcessingStatus
from backend.models.asset_metadata import AssetMetadata
from backend.models.processing_job import ProcessingJob, JobType, JobStatus
from backend.models.duplicate_cluster import DuplicateCluster, DuplicateClusterMember
from backend.models.collection import Collection, CollectionAsset
from backend.models.override import Override, OverrideType
from backend.models.assistant_run import AssistantRun, AssistantAction
from backend.models.export_job import ExportJob, ExportStatus

# Export all models and enums
__all__ = [
    "Base",
    "Event",
    "Asset",
    "AssetMetadata",
    "ProcessingJob",
    "DuplicateCluster",
    "DuplicateClusterMember",
    "Collection",
    "CollectionAsset",
    "Override",
    "AssistantRun",
    # Enums
    "ProcessingStatus",
    "JobType",
    "JobStatus",
    "OverrideType",
    "AssistantAction",
    "ExportStatus",
    "ExportJob"
]
