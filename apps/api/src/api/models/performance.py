"""Performance + engagement models.

Three tables, three responsibilities — kept separate so raw telemetry can
never leak into ranking:

  - `engagement_events`     ← raw per-platform metrics, append-only,
                              FK to exports (the telemetry anchor)
  - `experiment_groups`     ← A/B grouping primitive, used by future
                              experiment tooling
  - `performance_feature_sets`
                            ← derived, evaluation-layer output;
                              ranker-consumable. NEVER mutated from raw
                              events. Each row carries a `feature_version`
                              so the evaluator can evolve without losing
                              history.

Hard rule: anything that hits the ranker comes from `performance_feature_sets`.
Anything in `engagement_events` is reference data only.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, TimestampMixin, uuid_pk


# --- engagement_events -----------------------------------------------------


class EngagementMetricType(str, enum.Enum):
    """Canonical engagement metric vocabulary.

    Platforms ship a wider set of metrics — those that don't map cleanly
    are stored verbatim in `raw_payload` and ignored by the aggregator
    until they're triaged.
    """

    IMPRESSION = "impression"
    VIEW = "view"
    LIKE = "like"
    COMMENT = "comment"
    SHARE = "share"
    SAVE = "save"
    WATCH_TIME_S = "watch_time_s"
    COMPLETION_RATE = "completion_rate"
    REPLAY = "replay"


class EngagementEvent(Base, TimestampMixin):
    __tablename__ = "engagement_events"
    __table_args__ = (
        Index("ix_engagement_events_export_id", "export_id"),
        Index("ix_engagement_events_tenant_id_observed_at", "tenant_id", "observed_at"),
        Index("ix_engagement_events_platform_metric", "platform", "metric_type"),
        Index("ix_engagement_events_dedup", "export_id", "platform", "metric_type", "observed_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    export_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exports.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(nullable=False)
    # Hours since export publish at the time of observation; 1, 24, 168
    # are common. The aggregator buckets by this column.
    observation_window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


# --- experiment_groups -----------------------------------------------------


class ExperimentGroup(Base, TimestampMixin):
    """Sibling-relationship container.

    Used to group ExportArtifacts that are intentionally variants of one
    experiment (different hooks, different render styles, different
    captions). The ranker will eventually compare PerformanceFeatureSets
    that share an experiment_group_id.
    """

    __tablename__ = "experiment_groups"
    __table_args__ = (
        Index("ix_experiment_groups_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_experiment_groups_tenant_id_name", "tenant_id", "experiment_name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    experiment_name: Mapped[str] = mapped_column(String(128), nullable=False)
    experiment_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    group_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


# --- performance_feature_sets ---------------------------------------------


class MaturityState(str, enum.Enum):
    """How "trustworthy" an engagement signal is, by clip age + sample size."""

    FRESH = "fresh"          # < 1h or <50 impressions — barely any data
    MATURING = "maturing"    # 1h–24h, moderate sample
    STABLE = "stable"        # 24h–7d, enough data to act on
    DECAYED = "decayed"      # >7d, secondary signal


class PerformanceFeatureSet(Base, TimestampMixin):
    """Evaluator output — ranker-consumable derived features.

    `feature_version` lets the evaluator evolve (new normalization,
    different confidence model) without overwriting history. Each
    (export_id, feature_version) is a row.
    """

    __tablename__ = "performance_feature_sets"
    __table_args__ = (
        Index("ix_pfs_export_id_feature_version", "export_id", "feature_version", unique=True),
        Index("ix_pfs_tenant_id_evaluated_at", "tenant_id", "evaluated_at"),
        Index("ix_pfs_experiment_group_id", "experiment_group_id"),
        Index("ix_pfs_maturity_state", "maturity_state"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    export_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exports.id", ondelete="CASCADE"), nullable=False
    )
    experiment_group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("experiment_groups.id", ondelete="SET NULL"),
        nullable=True,
    )

    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    maturity_state: Mapped[str] = mapped_column(String(16), nullable=False)
    engagement_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # All normalized to 0..1 in the platform-normalization step. Raw
    # impression/view counts go in `derived_metadata` for audit.
    normalized_view_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_completion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_watch_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    replay_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    share_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Composite — the single number the ranker reads. 0..1.
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False)

    evaluated_at: Mapped[datetime] = mapped_column(nullable=False)
    derived_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
