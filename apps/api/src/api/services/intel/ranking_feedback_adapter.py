"""Ranking Feedback Adapter — READ-ONLY for raw data; CONTROLLED for scoring.

The ranker may **only** consume features that have passed through the
evaluation layer. This module is the *only* place the ranker is allowed
to fetch them from AND the *only* place a feedback adjustment can be
computed.

Phase 7 contract (unchanged):
  - `get_features_for_export(...)` → PerformanceFeatureView (read-only)
  - `get_features_for_experiment_group(...)` → list of views
  - `get_engagement_score_for_export(...)` → composite score

Phase 8 contract (new):
  - `apply_feedback_to_rank_score(base, view)` → FeedbackOutcome
    - structural-dominant: adjustment capped at ±`ENGAGEMENT_WEIGHT_CAP`
    - confidence-gated: zero adjustment when below `CONFIDENCE_THRESHOLD`
    - explainable: returns base, adjustment, final + human-readable text
    - reversible: pure function; same (base, view) → same outcome forever
    - feature_version tagged: the view's feature_version flows through

The ranker NEVER receives raw events. It NEVER sees `metric_value`,
`raw_payload`, `observed_at`. The view is frozen with 12 derived fields;
the outcome dataclass is also frozen.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import MaturityState, PerformanceFeatureSet


# --- Phase 8: controlled-feedback constants ------------------------------
#
# These are the explicit, audit-trail-visible guard values. Snapshots
# persist them so a future change to the constants is debuggable against
# historical runs.

ENGAGEMENT_WEIGHT_CAP = 0.15
"""Maximum absolute additive adjustment. 0.15 means engagement can move
the score by at most ±15% of the [0,1] range — structural ranking signals
always dominate."""

CONFIDENCE_THRESHOLD = 0.30
"""Minimum `engagement_confidence` for any adjustment. Below this, the
function returns adjustment=0 unconditionally. Fresh / low-sample
PerformanceFeatureSets contribute zero — the spike-resistance gate."""

NEUTRAL_ENGAGEMENT_MIDPOINT = 0.5
"""Engagement score 0.5 is neutral: no positive or negative pull. Above
0.5 pulls the rank up; below 0.5 pulls it down (proportionally)."""


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


# --- Phase 8: controlled feedback ------------------------------------------


@dataclass(frozen=True)
class FeedbackOutcome:
    """Pure-function output of `apply_feedback_to_rank_score`.

    Frozen + explicit fields. The ranker reads `final_rank_score` for
    sorting; the persistence layer writes the whole thing to a
    `ranking_snapshots` row for audit.
    """

    base_rank_score: float
    engagement_adjustment: float
    final_rank_score: float
    feedback_applied: bool
    feature_version: str
    confidence_threshold: float
    engagement_weight_cap: float
    explanation: str
    breakdown: dict


def apply_feedback_to_rank_score(
    base_rank_score: float,
    feature_view: PerformanceFeatureView | None,
) -> FeedbackOutcome:
    """Compute a deterministic, capped, confidence-gated adjustment.

    Math (kept simple and explicit on purpose):
      1. If feature_view is None → adjustment=0, feedback_applied=False.
      2. If view.engagement_confidence < CONFIDENCE_THRESHOLD → adjustment=0.
      3. Otherwise:
         centered = (engagement_score - 0.5) * 2          ∈ [-1, +1]
         scaled   = centered * confidence                  ∈ [-1, +1]
         capped   = scaled * ENGAGEMENT_WEIGHT_CAP         ∈ [-0.15, +0.15]
         final    = clamp(0, 1, base + capped)

    Guarantees:
      - structural-dominant: max |adjustment| = 0.15 (15% of [0,1])
      - confidence-gated: below threshold ⇒ 0
      - deterministic: same (base, view) → same outcome
      - explainable: breakdown carries all intermediates
      - never overwrites OmegaClips's base_rank_score
    """
    base = float(base_rank_score)
    feature_version = feature_view.feature_version if feature_view else "n/a"

    if feature_view is None:
        return FeedbackOutcome(
            base_rank_score=base,
            engagement_adjustment=0.0,
            final_rank_score=base,
            feedback_applied=False,
            feature_version=feature_version,
            confidence_threshold=CONFIDENCE_THRESHOLD,
            engagement_weight_cap=ENGAGEMENT_WEIGHT_CAP,
            explanation="No prior performance view supplied; ranker uses base score only.",
            breakdown={"reason": "no_feature_view"},
        )

    confidence = float(feature_view.engagement_confidence)
    if confidence < CONFIDENCE_THRESHOLD:
        return FeedbackOutcome(
            base_rank_score=base,
            engagement_adjustment=0.0,
            final_rank_score=base,
            feedback_applied=False,
            feature_version=feature_version,
            confidence_threshold=CONFIDENCE_THRESHOLD,
            engagement_weight_cap=ENGAGEMENT_WEIGHT_CAP,
            explanation=(
                f"Engagement confidence {confidence:.4f} below "
                f"threshold {CONFIDENCE_THRESHOLD}; no adjustment."
            ),
            breakdown={
                "reason": "below_confidence_threshold",
                "engagement_confidence": confidence,
                "confidence_threshold": CONFIDENCE_THRESHOLD,
                "engagement_score": float(feature_view.engagement_score),
                "maturity_state": feature_view.maturity_state.value,
            },
        )

    engagement = float(feature_view.engagement_score)
    centered = (engagement - NEUTRAL_ENGAGEMENT_MIDPOINT) * 2.0
    scaled = centered * confidence
    capped = max(
        -ENGAGEMENT_WEIGHT_CAP,
        min(ENGAGEMENT_WEIGHT_CAP, scaled * ENGAGEMENT_WEIGHT_CAP),
    )
    adjustment = round(capped, 4)
    final = round(max(0.0, min(1.0, base + adjustment)), 4)

    direction = "upward" if adjustment > 0 else ("downward" if adjustment < 0 else "neutral")
    explanation = (
        f"Confidence={confidence:.4f} above threshold {CONFIDENCE_THRESHOLD}; "
        f"engagement_score={engagement:.4f} centered around 0.5; "
        f"adjustment {direction} {adjustment:+.4f} (cap ±{ENGAGEMENT_WEIGHT_CAP}); "
        f"base {base:.4f} → final {final:.4f}."
    )
    breakdown = {
        "engagement_confidence": confidence,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "engagement_score": engagement,
        "maturity_state": feature_view.maturity_state.value,
        "centered": centered,
        "scaled_by_confidence": scaled,
        "capped": adjustment,
        "engagement_weight_cap": ENGAGEMENT_WEIGHT_CAP,
        "neutral_midpoint": NEUTRAL_ENGAGEMENT_MIDPOINT,
        "direction": direction,
    }

    return FeedbackOutcome(
        base_rank_score=base,
        engagement_adjustment=adjustment,
        final_rank_score=final,
        feedback_applied=adjustment != 0.0,
        feature_version=feature_version,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        engagement_weight_cap=ENGAGEMENT_WEIGHT_CAP,
        explanation=explanation,
        breakdown=breakdown,
    )


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
