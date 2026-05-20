"""UsageEvent — canonical metering log for billing + analytics."""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, TimestampMixin, uuid_pk


class UsageEventType(str, enum.Enum):
    UPLOAD_CREATED = "upload_created"
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    RANKING_STARTED = "ranking_started"
    RANKING_COMPLETED = "ranking_completed"
    CANDIDATE_CREATED = "candidate_created"
    DIRECTOR_PLAN_CREATED = "director_plan_created"
    RENDER_STARTED = "render_started"
    RENDER_COMPLETED = "render_completed"
    EXPORT_CREATED = "export_created"
    ENGAGEMENT_INGESTED = "engagement_ingested"
    EVALUATION_COMPLETED = "evaluation_completed"
    RANKING_FEEDBACK_APPLIED = "ranking_feedback_applied"
    CREDITS_RESERVED = "credits_reserved"
    CREDITS_CONSUMED = "credits_consumed"
    CREDITS_REFUNDED = "credits_refunded"
    JOB_FAILED = "job_failed"
    USER_APPROVED_CLIP = "user_approved_clip"
    # --- operational audit (Phase 10) -------------------------------
    TRANSITION_ACCEPTED = "transition_accepted"
    TRANSITION_REJECTED = "transition_rejected"
    TRANSITION_FORCED = "transition_forced"
    WORKER_STARTED = "worker_started"
    WORKER_HEARTBEAT = "worker_heartbeat"
    WORKER_STALE_DETECTED = "worker_stale_detected"
    WORKER_RETRY_INITIATED = "worker_retry_initiated"
    IDEMPOTENCY_REPLAY = "idempotency_replay"
    R2_UPLOAD_COMPLETED = "r2_upload_completed"
    R2_UPLOAD_VERIFIED = "r2_upload_verified"


class UsageEvent(Base, TimestampMixin):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_usage_events_event_type", "event_type"),
        Index("ix_usage_events_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    upload_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="count")
    estimated_cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stripe_meter_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
