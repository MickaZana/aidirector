"""PlanCorrection model — records user edits to DirectorPlans.

Every time a user adjusts a DirectorPlan (reorder, change pacing/style,
add/remove candidates), a PlanCorrection row is created. This enables:

1. **Replay safety**: the pre- and post-correction plans are snapshotted
   so the pipeline can be re-run with either version.
2. **Learning loop**: aggregated corrections across all tenants become
   few-shot examples for the Claude enrichment prompt (Sprint 5.3).
3. **Audit trail**: who changed what, when, and why.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, TimestampMixin, uuid_pk


class PlanCorrection(Base, TimestampMixin):
    __tablename__ = "plan_corrections"
    __table_args__ = (
        Index("ix_plan_corrections_tenant_id", "tenant_id"),
        Index("ix_plan_corrections_job_id", "job_id"),
        Index("ix_plan_corrections_plan_id", "plan_id"),
        Index("ix_plan_corrections_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("director_plans.id", ondelete="CASCADE"), nullable=False
    )

    # Snapshot of the plan before and after correction
    original_plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    corrected_plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Structured diff metadata
    correction_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    """One of: 'reorder', 'pacing_change', 'style_change', 'candidate_removed',
    'candidate_added', 'crop_change', 'multiple'."""

    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Optional user-typed explanation for the correction."""

    applied_at: Mapped[datetime] = mapped_column(nullable=False)
    """When the correction was applied (may differ from created_at if
    backfilled from a webhook or batch import)."""
