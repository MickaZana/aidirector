"""Evaluation Layer — derived features that the ranker is allowed to read.

Sits between `engagement_aggregation` (raw) and the ranker feedback
adapter. Hard rules:
  - Reads from `engagement_aggregation.RawAggregation` only — never
    directly from `engagement_events` rows.
  - Writes to `performance_feature_sets`.
  - Re-evaluable: re-running over the same aggregation produces the same
    feature row (modulo PK/timestamps).
  - Feature-version-aware: each call writes a new row keyed on
    (export_id, feature_version) so the evaluator can evolve without
    losing history.

What it does:
  - Classifies maturity from clip age + sample size
  - Suppresses outliers a second time at the feature level (over the
    aggregator's own outlier handling)
  - Normalises raw counts to 0..1 per platform (impression-relative)
  - Weights by confidence (sample size × maturity)
  - Composes a single 0..1 `engagement_score` the ranker can consume
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import (
    ExportArtifact,
    MaturityState,
    PerformanceFeatureSet,
    UsageEventType,
)
from api.services.engagement_aggregation import (
    RawAggregation,
    WindowedMetric,
    aggregate_engagement_for_export,
)
from api.services.usage_events import emit_usage_event


CURRENT_FEATURE_VERSION = "v1"

# Per-platform impression-relative baselines for normalisation. These are
# rough first-pass values; the data flywheel tunes them. Keep them in one
# place so future tuning is one edit.
_PLATFORM_BASELINES: dict[str, dict[str, float]] = {
    "youtube_shorts": {
        "view_rate": 0.6,             # views / impressions
        "completion_rate": 0.5,
        "share_rate": 0.02,
        "replay_rate": 0.05,
    },
    "tiktok": {
        "view_rate": 0.8,
        "completion_rate": 0.4,
        "share_rate": 0.03,
        "replay_rate": 0.08,
    },
    "instagram_reels": {
        "view_rate": 0.55,
        "completion_rate": 0.45,
        "share_rate": 0.02,
        "replay_rate": 0.06,
    },
    "x": {
        "view_rate": 0.45,
        "completion_rate": 0.35,
        "share_rate": 0.015,
        "replay_rate": 0.04,
    },
}

# Confidence model: max confidence at large samples + mature state.
_MIN_SAMPLES_FOR_FULL_CONFIDENCE = 1000
_MATURITY_CONFIDENCE_WEIGHT: dict[MaturityState, float] = {
    MaturityState.FRESH: 0.2,
    MaturityState.MATURING: 0.6,
    MaturityState.STABLE: 1.0,
    MaturityState.DECAYED: 0.7,
}


@dataclass(frozen=True)
class EvaluatedFeatures:
    """Frozen evaluator output — the persistence layer mints the DB row."""

    export_id: uuid.UUID
    tenant_id: uuid.UUID
    experiment_group_id: uuid.UUID | None
    feature_version: str
    maturity_state: MaturityState
    engagement_confidence: float
    normalized_view_rate: float | None
    normalized_completion_rate: float | None
    normalized_watch_time: float | None
    replay_rate: float | None
    share_rate: float | None
    engagement_score: float
    evaluated_at: datetime
    derived_metadata: dict


def evaluate_export(
    db: Session,
    *,
    export: ExportArtifact,
    aggregation: RawAggregation | None = None,
    experiment_group_id: uuid.UUID | None = None,
    feature_version: str = CURRENT_FEATURE_VERSION,
    evaluated_at: datetime | None = None,
) -> EvaluatedFeatures:
    """Produce derived ranker-safe features for one export."""
    if aggregation is None:
        aggregation = aggregate_engagement_for_export(db, export_id=export.id)
    evaluated_at = evaluated_at or datetime.now(timezone.utc)

    # Combine all platforms-and-windows into one feature row.
    impressions = _sum_metric(aggregation.windows, "impression")
    views = _sum_metric(aggregation.windows, "view")
    completions_rate_sum = _sum_metric(aggregation.windows, "completion_rate")
    watch_time = _sum_metric(aggregation.windows, "watch_time_s")
    replays = _sum_metric(aggregation.windows, "replay")
    shares = _sum_metric(aggregation.windows, "share")
    sample_size = sum(w.sample_size for w in aggregation.windows)
    primary_platform = aggregation.windows[0].platform if aggregation.windows else export.platform

    age_hours = _hours_since(export.created_at, evaluated_at)
    maturity = _classify_maturity(age_hours=age_hours, sample_size=sample_size)

    norm_view = _normalize(views, impressions, primary_platform, "view_rate")
    norm_completion = _normalize_completion_rate(
        completions_rate_sum, sample_size, primary_platform
    )
    norm_watch = _normalize_watch_time(watch_time, export.artifact_metadata)
    replay_rate = _safe_ratio(replays, views) if views else None
    share_rate = _safe_ratio(shares, views) if views else None

    confidence = _compute_confidence(maturity=maturity, sample_size=sample_size)

    # Composite engagement score. Weights are explicit and tunable.
    components = {
        "view": (norm_view, 0.30),
        "completion": (norm_completion, 0.30),
        "watch": (norm_watch, 0.15),
        "replay": (replay_rate, 0.10),
        "share": (share_rate, 0.15),
    }
    engagement_score = _weighted_score(components, confidence=confidence)

    return EvaluatedFeatures(
        export_id=export.id,
        tenant_id=export.tenant_id,
        experiment_group_id=experiment_group_id,
        feature_version=feature_version,
        maturity_state=maturity,
        engagement_confidence=confidence,
        normalized_view_rate=norm_view,
        normalized_completion_rate=norm_completion,
        normalized_watch_time=norm_watch,
        replay_rate=replay_rate,
        share_rate=share_rate,
        engagement_score=engagement_score,
        evaluated_at=evaluated_at,
        derived_metadata={
            "primary_platform": primary_platform,
            "age_hours": age_hours,
            "total_events_seen": aggregation.total_events_seen,
            "dedup_dropped": aggregation.dedup_dropped,
            "outliers_dropped": aggregation.outliers_dropped,
            "sample_size": sample_size,
            "windows_observed": [
                {
                    "platform": w.platform,
                    "observation_window_hours": w.observation_window_hours,
                    "sample_size": w.sample_size,
                    "metric_totals": w.metric_totals,
                }
                for w in aggregation.windows
            ],
            "components": {k: {"value": v[0], "weight": v[1]} for k, v in components.items()},
        },
    )


def persist_features(
    db: Session,
    *,
    features: EvaluatedFeatures,
    job_id: uuid.UUID | None = None,
    upload_id: uuid.UUID | None = None,
) -> PerformanceFeatureSet:
    """INSERT (or update by (export_id, feature_version)) + emit
    EVALUATION_COMPLETED."""
    existing = db.execute(
        select(PerformanceFeatureSet).where(
            PerformanceFeatureSet.export_id == features.export_id,
            PerformanceFeatureSet.feature_version == features.feature_version,
        )
    ).scalar_one_or_none()

    if existing is None:
        row = PerformanceFeatureSet(
            id=uuid.uuid4(),
            tenant_id=features.tenant_id,
            export_id=features.export_id,
            experiment_group_id=features.experiment_group_id,
            feature_version=features.feature_version,
            maturity_state=features.maturity_state.value,
            engagement_confidence=features.engagement_confidence,
            normalized_view_rate=features.normalized_view_rate,
            normalized_completion_rate=features.normalized_completion_rate,
            normalized_watch_time=features.normalized_watch_time,
            replay_rate=features.replay_rate,
            share_rate=features.share_rate,
            engagement_score=features.engagement_score,
            evaluated_at=features.evaluated_at,
            derived_metadata=features.derived_metadata,
        )
        db.add(row)
    else:
        existing.experiment_group_id = features.experiment_group_id
        existing.maturity_state = features.maturity_state.value
        existing.engagement_confidence = features.engagement_confidence
        existing.normalized_view_rate = features.normalized_view_rate
        existing.normalized_completion_rate = features.normalized_completion_rate
        existing.normalized_watch_time = features.normalized_watch_time
        existing.replay_rate = features.replay_rate
        existing.share_rate = features.share_rate
        existing.engagement_score = features.engagement_score
        existing.evaluated_at = features.evaluated_at
        existing.derived_metadata = features.derived_metadata
        row = existing
    db.flush()

    emit_usage_event(
        db,
        tenant_id=features.tenant_id,
        upload_id=upload_id,
        job_id=job_id,
        event_type=UsageEventType.EVALUATION_COMPLETED,
        unit="feature_set",
        metadata={
            "export_id": str(features.export_id),
            "feature_version": features.feature_version,
            "maturity_state": features.maturity_state.value,
            "engagement_confidence": features.engagement_confidence,
            "engagement_score": features.engagement_score,
            "experiment_group_id": (
                str(features.experiment_group_id)
                if features.experiment_group_id is not None
                else None
            ),
            "sample_size": features.derived_metadata.get("sample_size"),
        },
    )
    return row


# --- Pure helpers ----------------------------------------------------------


def _classify_maturity(*, age_hours: float, sample_size: int) -> MaturityState:
    if age_hours < 1 or sample_size < 50:
        return MaturityState.FRESH
    if age_hours < 24:
        return MaturityState.MATURING
    if age_hours < 24 * 7:
        return MaturityState.STABLE
    return MaturityState.DECAYED


def _compute_confidence(*, maturity: MaturityState, sample_size: int) -> float:
    """0..1. Combines sample-size confidence with maturity weight."""
    sample_confidence = min(1.0, sample_size / float(_MIN_SAMPLES_FOR_FULL_CONFIDENCE))
    maturity_weight = _MATURITY_CONFIDENCE_WEIGHT[maturity]
    return round(min(1.0, max(0.0, sample_confidence * maturity_weight)), 4)


def _hours_since(reference: datetime, now: datetime) -> float:
    delta: timedelta
    # Both datetimes might be naive depending on dialect; coerce.
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = now - reference
    return max(0.0, delta.total_seconds() / 3600.0)


def _normalize(numerator: float, denominator: float, platform: str, baseline_key: str) -> float | None:
    if denominator <= 0:
        return None
    rate = numerator / denominator
    baseline = _PLATFORM_BASELINES.get(platform, {}).get(baseline_key)
    if baseline is None or baseline <= 0:
        return round(min(1.0, max(0.0, rate)), 4)
    # Normalise by the per-platform baseline so each platform competes on
    # its own curve. 1.0 == hitting baseline; we cap at 1.0 to avoid
    # virality outliers dominating the score.
    return round(min(1.0, max(0.0, rate / (baseline * 2.0))), 4)


def _normalize_completion_rate(
    sum_rate: float, sample_size: int, platform: str
) -> float | None:
    if sample_size <= 0:
        return None
    avg = sum_rate / sample_size
    baseline = _PLATFORM_BASELINES.get(platform, {}).get("completion_rate")
    if baseline is None or baseline <= 0:
        return round(min(1.0, max(0.0, avg)), 4)
    return round(min(1.0, max(0.0, avg / (baseline * 2.0))), 4)


def _normalize_watch_time(total_watch_time_s: float, artifact_metadata: dict) -> float | None:
    if total_watch_time_s <= 0:
        return None
    clip_duration = float(artifact_metadata.get("duration_s") or 0.0)
    if clip_duration <= 0:
        return round(min(1.0, total_watch_time_s / 60.0), 4)
    # avg-watch-time-per-impression / clip-duration → 0..1
    return round(min(1.0, max(0.0, total_watch_time_s / (clip_duration * 1000))), 4)


def _safe_ratio(a: float, b: float) -> float:
    if b <= 0:
        return 0.0
    return round(min(1.0, max(0.0, a / b)), 4)


def _weighted_score(
    components: dict[str, tuple[float | None, float]], *, confidence: float
) -> float:
    total_weight = 0.0
    total_value = 0.0
    for value, weight in components.values():
        if value is None:
            continue
        total_value += value * weight
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    raw = total_value / total_weight
    return round(min(1.0, max(0.0, raw * confidence)), 4)


def _sum_metric(windows: Iterable[WindowedMetric], metric: str) -> float:
    return sum(w.metric_totals.get(metric, 0.0) for w in windows)
