"""Pipeline models: Upload, Job, Scene, ClipCandidate, DirectorPlan, RenderJob, RenderOutput.

Every row is tenant-scoped. JSON columns store the OmegaClips signal payloads
and director plan output without leaking schema details into Postgres columns.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models.base import Base, TimestampMixin, uuid_pk


class UploadStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    INGESTING = "ingesting"
    READY = "ready"
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    EXPIRED = "expired"
    """Marked for deletion by retention policy. Kept briefly for audit."""


class RenderJobStatus(str, enum.Enum):
    QUEUED = "queued"
    RENDERING = "rendering"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"


class Upload(Base, TimestampMixin):
    __tablename__ = "uploads"
    __table_args__ = (
        Index("ix_uploads_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_uploads_status", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    r2_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    bytes: Mapped[int | None] = mapped_column(nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    sport: Mapped[str] = mapped_column(String(32), nullable=False, default="football")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=UploadStatus.PENDING.value
    )
    upload_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_tenant_id_status", "tenant_id", "status"),
        Index("ix_jobs_upload_id", "upload_id"),
        Index("ix_jobs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    intent: Mapped[str] = mapped_column(String(32), nullable=False, default="analyze")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JobStatus.QUEUED.value)
    omegaclips_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intel_submodule_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cost_budget_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    cost_actual_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # --- Phase 10 operational fields -----------------------------------
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # --- Sprint 5.4: pipeline timing -----------------------------------
    pipeline_timing: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """Per-stage timing breakdown. Shape:
    {
      "analysis_started": "ISO8601",
      "analysis_completed": "ISO8601",
      "director_plan_started": "ISO8601",
      "director_plan_completed": "ISO8601",
      "render_batch_started": "ISO8601",
      "render_batch_completed": "ISO8601",
      "render_count": 6,
      "render_parallel_count": 6,
      "render_total_elapsed_s": 45.2,
      "render_max_elapsed_s": 12.3,
      "total_pipeline_s": 142.1,
    }"""


class Scene(Base, TimestampMixin):
    __tablename__ = "scenes"
    __table_args__ = (
        Index("ix_scenes_job_id", "job_id"),
        Index("ix_scenes_kind", "kind"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    t_start: Mapped[float] = mapped_column(Float, nullable=False)
    t_end: Mapped[float] = mapped_column(Float, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    arc_position: Mapped[str | None] = mapped_column(String(16), nullable=True)
    intensity: Mapped[float | None] = mapped_column(Float, nullable=True)
    importance: Mapped[float | None] = mapped_column(Float, nullable=True)
    signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ClipCandidate(Base, TimestampMixin):
    __tablename__ = "clip_candidates"
    __table_args__ = (
        Index("ix_clip_candidates_job_id", "job_id"),
        Index("ix_clip_candidates_scene_id", "scene_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True
    )
    t_start: Mapped[float] = mapped_column(Float, nullable=False)
    t_end: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    platform_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    virality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    novelty_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class DirectorPlan(Base, TimestampMixin):
    __tablename__ = "director_plans"
    __table_args__ = (
        Index("ix_director_plans_job_id", "job_id"),
        Index("ix_director_plans_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class RenderJob(Base, TimestampMixin):
    __tablename__ = "render_jobs"
    __table_args__ = (
        Index("ix_render_jobs_job_id", "job_id"),
        Index("ix_render_jobs_status", "status"),
        Index("ix_render_jobs_created_at", "created_at"),
        Index("ix_render_jobs_idempotency_key", "idempotency_key", unique=True),
        Index("ix_render_jobs_heartbeat_at", "heartbeat_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("clip_candidates.id", ondelete="CASCADE"), nullable=False
    )
    pipeline: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RenderJobStatus.QUEUED.value
    )
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    gpu_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # --- Phase 10 operational fields -----------------------------------
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # sha256(candidate_id|variant_id|render_style|version) — UNIQUE.
    # Re-running the same render fixture must not produce a duplicate row.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RenderOutput(Base, TimestampMixin):
    __tablename__ = "render_outputs"
    __table_args__ = (Index("ix_render_outputs_render_job_id", "render_job_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    render_job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("render_jobs.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    r2_key: Mapped[str] = mapped_column(String(512), nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(8), nullable=False)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    bytes: Mapped[int | None] = mapped_column(nullable=True)
    output_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
