"""RankingSnapshot — explainable, auditable, replayable ranking record.

One row per (candidate × ranking-run × feature_version). Captures the
structural and feedback components of the final rank score separately so
later changes are debuggable and rollback-safe.

Hard rules baked into the schema:
  - `base_rank_score`     ← what OmegaClips ranker computed; never overwritten
  - `engagement_adjustment`← delta applied (0 when feedback off or below
                            confidence threshold)
  - `final_rank_score`    ← clamp(0,1, base + adjustment)
  - `feedback_applied`    ← bool, true only when adjustment != 0
  - `confidence_threshold`/`engagement_weight_cap` — what guard values were
                            active for this snapshot (audit trail for tuning)
  - `explanation`         ← short human-readable line; full math in
                            `snapshot_metadata`

Re-running the ranker with the same inputs MUST produce the same
(base, adjustment, final). Unique index on (candidate_id, feature_version)
enforces idempotent upsert.
"""
from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, TimestampMixin, uuid_pk


class RankingSnapshot(Base, TimestampMixin):
    __tablename__ = "ranking_snapshots"
    __table_args__ = (
        Index(
            "ix_ranking_snapshots_candidate_feature_version",
            "candidate_id", "feature_version", unique=True,
        ),
        Index("ix_ranking_snapshots_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_ranking_snapshots_feedback_applied", "feedback_applied"),
        Index("ix_ranking_snapshots_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("clip_candidates.id", ondelete="CASCADE"), nullable=False
    )
    # The job that produced this candidate (for replay / regression sets)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    # Optional FK to the export whose engagement informed this snapshot.
    # Null when feedback wasn't applied OR when feedback came from an
    # aggregate over multiple priors.
    source_export_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("exports.id", ondelete="SET NULL"), nullable=True
    )

    base_rank_score: Mapped[float] = mapped_column(Float, nullable=False)
    engagement_adjustment: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_rank_score: Mapped[float] = mapped_column(Float, nullable=False)

    feature_version: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    engagement_weight_cap: Mapped[float] = mapped_column(Float, nullable=False)

    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
