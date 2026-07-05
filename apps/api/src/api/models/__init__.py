"""SQLAlchemy ORM models for AI Director.

All models inherit from `Base` so `target_metadata = Base.metadata` in
`alembic/env.py` picks them up for autogeneration.
"""

from api.models.base import Base, TimestampMixin
from api.models.tenancy import Tenant, User
from api.models.pipeline import (
    ClipCandidate,
    DirectorPlan,
    Job,
    JobStatus,
    RenderJob,
    RenderJobStatus,
    RenderOutput,
    Scene,
    Upload,
    UploadStatus,
)
from api.models.exports import ExportArtifact, ExportArtifactStatus
from api.models.performance import (
    EngagementEvent,
    EngagementMetricType,
    ExperimentGroup,
    MaturityState,
    PerformanceFeatureSet,
)
from api.models.ranking import RankingSnapshot
from api.models.usage import UsageEvent, UsageEventType
from api.models.brief_templates import BriefTemplate
from api.models.corrections import PlanCorrection

__all__ = [
    "Base",
    "TimestampMixin",
    "Tenant",
    "User",
    "Upload",
    "UploadStatus",
    "Job",
    "JobStatus",
    "Scene",
    "ClipCandidate",
    "DirectorPlan",
    "RenderJob",
    "RenderJobStatus",
    "RenderOutput",
    "ExportArtifact",
    "ExportArtifactStatus",
    "EngagementEvent",
    "EngagementMetricType",
    "ExperimentGroup",
    "MaturityState",
    "PerformanceFeatureSet",
    "RankingSnapshot",
    "UsageEvent",
    "UsageEventType",
    "BriefTemplate",
    "PlanCorrection",
]
