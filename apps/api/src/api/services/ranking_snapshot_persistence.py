"""Persist a RankingSnapshot row + emit RANKING_FEEDBACK_APPLIED.

One snapshot per (candidate × feature_version). UNIQUE index on those two
columns enforces idempotent upsert — replaying the ranker for the same
candidate updates the row in place instead of inserting a duplicate. This
keeps audit history clean and rollbacks safe.

Caller flow (worker or probe):
  1. Run `clip_ranking_adapter.rank_clip_candidates(..., prior_performance=…)`.
  2. For each ranked candidate, the `scores` dict carries the full
     feedback breakdown.
  3. Pass the candidate's ORM row + scores into `persist_ranking_snapshot(…)`.
  4. The persistence layer writes the snapshot + emits one usage event
     per snapshot.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import (
    ClipCandidate,
    Job,
    RankingSnapshot,
    UsageEventType,
)
from api.services.usage_events import emit_usage_event


def persist_ranking_snapshot(
    db: Session,
    *,
    job: Job,
    candidate: ClipCandidate,
    scores: dict,
    source_export_id: uuid.UUID | None = None,
) -> RankingSnapshot:
    """Upsert one snapshot keyed by (candidate_id, feature_version)."""
    feature_version = str(scores.get("feature_version") or "n/a")
    base_rank_score = float(scores.get("base_rank_score") or 0.0)
    engagement_adjustment = float(scores.get("engagement_adjustment") or 0.0)
    final_rank_score = float(scores.get("final_rank_score") or base_rank_score)
    feedback_applied = bool(scores.get("feedback_applied") or False)
    confidence_threshold = float(scores.get("confidence_threshold") or 0.0)
    engagement_weight_cap = float(scores.get("engagement_weight_cap") or 0.0)
    explanation = str(scores.get("feedback_explanation") or "")
    breakdown = scores.get("feedback_breakdown") or {}

    existing = db.execute(
        select(RankingSnapshot).where(
            RankingSnapshot.candidate_id == candidate.id,
            RankingSnapshot.feature_version == feature_version,
        )
    ).scalar_one_or_none()

    if existing is None:
        row = RankingSnapshot(
            id=uuid.uuid4(),
            tenant_id=candidate.tenant_id,
            candidate_id=candidate.id,
            job_id=job.id,
            source_export_id=source_export_id,
            base_rank_score=base_rank_score,
            engagement_adjustment=engagement_adjustment,
            final_rank_score=final_rank_score,
            feature_version=feature_version,
            feedback_applied=feedback_applied,
            confidence_threshold=confidence_threshold,
            engagement_weight_cap=engagement_weight_cap,
            explanation=explanation,
            snapshot_metadata={
                "breakdown": breakdown,
                "scene_index": scores.get("scene_index"),
                "ranking_intent": scores.get("ranking_intent"),
                "ranking_engine": scores.get("ranking_engine"),
                "source_previous_score": scores.get("source_previous_score"),
                "source_new_score": scores.get("source_new_score"),
            },
        )
        db.add(row)
    else:
        # Upsert: same identity → update in place, preserve audit history.
        existing.job_id = job.id
        existing.source_export_id = source_export_id
        existing.base_rank_score = base_rank_score
        existing.engagement_adjustment = engagement_adjustment
        existing.final_rank_score = final_rank_score
        existing.feedback_applied = feedback_applied
        existing.confidence_threshold = confidence_threshold
        existing.engagement_weight_cap = engagement_weight_cap
        existing.explanation = explanation
        existing.snapshot_metadata = {
            "breakdown": breakdown,
            "scene_index": scores.get("scene_index"),
            "ranking_intent": scores.get("ranking_intent"),
            "ranking_engine": scores.get("ranking_engine"),
            "source_previous_score": scores.get("source_previous_score"),
            "source_new_score": scores.get("source_new_score"),
        }
        row = existing
    db.flush()

    emit_usage_event(
        db,
        tenant_id=candidate.tenant_id,
        job_id=job.id,
        event_type=UsageEventType.RANKING_FEEDBACK_APPLIED,
        unit="snapshot",
        metadata={
            "candidate_id": str(candidate.id),
            "feature_version": feature_version,
            "feedback_applied": feedback_applied,
            "base_rank_score": base_rank_score,
            "engagement_adjustment": engagement_adjustment,
            "final_rank_score": final_rank_score,
            "confidence_threshold": confidence_threshold,
            "engagement_weight_cap": engagement_weight_cap,
            "source_export_id": str(source_export_id) if source_export_id else None,
        },
    )
    return row
