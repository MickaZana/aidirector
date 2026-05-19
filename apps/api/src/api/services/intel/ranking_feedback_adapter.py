"""Ranking Feedback Adapter — READ-ONLY.

The hardest design rule in Phase 7: the ranker may **only** consume
features that have passed through the evaluation layer. This module is
the *only* place the ranker is allowed to fetch them from.

It exposes:
  - `get_features_for_export(export_id)` → one PerformanceFeatureSet view
  - `get_features_for_experiment_group(...)` → siblings in an A/B group
  - `get_engagement_score_for_export(...)` → the single composite number

It does NOT expose:
  - raw engagement_events
  - raw metric_totals
  - raw observation windows
  - anything that hasn't been normalised + confidence-weighted

The adapter is a Protocol implementation point: future ranking adapters
(`clip_ranking_adapter`, `director_plan_builder`) import THIS module to
read engagement features. They never touch `engagement_events` directly.

**This module does not modify any ranker logic in Phase 7.** That's
deliberate. Phase 8 wires the read at the ranker call site.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import MaturityState, PerformanceFeatureSet


@dataclass(frozen=True)
class PerformanceFeatureView:
    """Read-only projection over PerformanceFeatureSet.

    Frozen + only-derived-fields. Even if a future caller wanted to
    bypass and reach into raw metrics, the view doesn't offer them.
    """

    export_id: uuid.UUID
    tenant_id: uuid.UUID
    feature_version: str
    maturity_state: MaturityState
    engagement_confidence: float
    normalized_view_rate: float | None
    normalized_completion_rate: float | None
    normalized_watch_time: float | None
    replay_rate: float | None
    share_rate: float | None
    engagement_score: float
    experiment_group_id: uuid.UUID | None


def get_features_for_export(
    db: Session,
    *,
    export_id: uuid.UUID,
    feature_version: str = "v1",
) -> PerformanceFeatureView | None:
    row = db.execute(
        select(PerformanceFeatureSet).where(
            PerformanceFeatureSet.export_id == export_id,
            PerformanceFeatureSet.feature_version == feature_version,
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return _to_view(row)


def get_features_for_experiment_group(
    db: Session,
    *,
    experiment_group_id: uuid.UUID,
    feature_version: str = "v1",
) -> list[PerformanceFeatureView]:
    rows = (
        db.execute(
            select(PerformanceFeatureSet).where(
                PerformanceFeatureSet.experiment_group_id == experiment_group_id,
                PerformanceFeatureSet.feature_version == feature_version,
            )
        )
        .scalars()
        .all()
    )
    return [_to_view(r) for r in rows]


def get_engagement_score_for_export(
    db: Session,
    *,
    export_id: uuid.UUID,
    feature_version: str = "v1",
) -> float | None:
    view = get_features_for_export(
        db, export_id=export_id, feature_version=feature_version
    )
    return None if view is None else view.engagement_score


# --- Internals --------------------------------------------------------------


def _to_view(row: PerformanceFeatureSet) -> PerformanceFeatureView:
    return PerformanceFeatureView(
        export_id=row.export_id,
        tenant_id=row.tenant_id,
        feature_version=row.feature_version,
        maturity_state=MaturityState(row.maturity_state),
        engagement_confidence=row.engagement_confidence,
        normalized_view_rate=row.normalized_view_rate,
        normalized_completion_rate=row.normalized_completion_rate,
        normalized_watch_time=row.normalized_watch_time,
        replay_rate=row.replay_rate,
        share_rate=row.share_rate,
        engagement_score=row.engagement_score,
        experiment_group_id=row.experiment_group_id,
    )
