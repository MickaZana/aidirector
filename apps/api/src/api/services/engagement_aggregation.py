"""Engagement aggregation — raw events → bucketed rollups.

The first half of the *measure → improve* pipeline. Reads from
`engagement_events`, buckets by observation window, deduplicates,
produces a `RawAggregation` payload for the evaluation layer.

Hard rules:
  - Does NOT write to `performance_feature_sets` (that's evaluation's job).
  - Does NOT modify ranker state.
  - Replay-safe: re-running aggregation over the same events yields the
    same rollup byte-for-byte.

What it DOES handle:
  - Deduplication on (export_id, platform, metric_type, observed_at) —
    if the same event arrives twice from two ingestion sources, we count
    it once.
  - Window bucketing — one rollup row per (export_id, platform,
    observation_window_hours).
  - Outlier dropping at the raw level (negative metric_value, NaN, inf).
"""
from __future__ import annotations

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import EngagementEvent, ExportArtifact


@dataclass(frozen=True)
class WindowedMetric:
    """One rollup line: (platform, window) → {metric: value}."""

    platform: str
    observation_window_hours: int
    metric_totals: dict[str, float]
    sample_size: int
    earliest_observed_at: datetime
    latest_observed_at: datetime


@dataclass(frozen=True)
class RawAggregation:
    """Aggregator output — frozen for replay-safety."""

    export_id: uuid.UUID
    windows: tuple[WindowedMetric, ...]
    total_events_seen: int
    dedup_dropped: int
    outliers_dropped: int


def aggregate_engagement_for_export(
    db: Session,
    *,
    export_id: uuid.UUID,
) -> RawAggregation:
    """Bucket all engagement_events for an export into (platform, window) rollups."""
    rows = (
        db.execute(
            select(EngagementEvent)
            .where(EngagementEvent.export_id == export_id)
            .order_by(EngagementEvent.observed_at.asc())
        )
        .scalars()
        .all()
    )
    return _aggregate_rows(export_id=export_id, rows=rows)


def aggregate_engagement_for_artifact(
    db: Session,
    *,
    artifact: ExportArtifact,
) -> RawAggregation:
    return aggregate_engagement_for_export(db, export_id=artifact.id)


# --- Internals --------------------------------------------------------------


def _aggregate_rows(
    *, export_id: uuid.UUID, rows: list[EngagementEvent]
) -> RawAggregation:
    """Deterministic, in-memory aggregation. Same input → same output."""
    seen: set[tuple[str, str, str]] = set()  # (platform, metric, ISO-observed)
    outliers_dropped = 0
    dedup_dropped = 0

    # bucket[(platform, window)] = {metric: total, "_samples": count, ...}
    bucket: dict[tuple[str, int], _Bucket] = defaultdict(_Bucket)

    for row in rows:
        if _is_outlier(row.metric_value):
            outliers_dropped += 1
            continue
        dedup_key = (row.platform, row.metric_type, row.observed_at.isoformat())
        if dedup_key in seen:
            dedup_dropped += 1
            continue
        seen.add(dedup_key)
        bucket[(row.platform, row.observation_window_hours)].add(row)

    windows = tuple(
        WindowedMetric(
            platform=platform,
            observation_window_hours=window,
            metric_totals=dict(b.metric_totals),
            sample_size=b.sample_size,
            earliest_observed_at=b.earliest_observed_at,
            latest_observed_at=b.latest_observed_at,
        )
        for (platform, window), b in sorted(bucket.items())
    )

    return RawAggregation(
        export_id=export_id,
        windows=windows,
        total_events_seen=len(rows),
        dedup_dropped=dedup_dropped,
        outliers_dropped=outliers_dropped,
    )


def _is_outlier(value: float) -> bool:
    """Hard rejections at the raw level. Evaluation layer handles the rest."""
    if value is None:
        return True
    if math.isnan(value) or math.isinf(value):
        return True
    if value < 0:
        return True
    return False


class _Bucket:
    """In-memory accumulator. Not exported."""

    def __init__(self) -> None:
        self.metric_totals: dict[str, float] = defaultdict(float)
        self.sample_size: int = 0
        self.earliest_observed_at: datetime | None = None  # type: ignore[assignment]
        self.latest_observed_at: datetime | None = None  # type: ignore[assignment]

    def add(self, row: EngagementEvent) -> None:
        self.metric_totals[row.metric_type] += float(row.metric_value)
        self.sample_size += 1
        if self.earliest_observed_at is None or row.observed_at < self.earliest_observed_at:
            self.earliest_observed_at = row.observed_at
        if self.latest_observed_at is None or row.observed_at > self.latest_observed_at:
            self.latest_observed_at = row.observed_at
