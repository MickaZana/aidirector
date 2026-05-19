"""Ranking Feedback Worker — Modal-side wrapper over the controlled-feedback path.

Zero math, zero feedback policy. Receives a job_id + a mapping of
{scene_index → PerformanceFeatureView dict}, re-runs the ranking adapter
with the feedback enabled, persists one RankingSnapshot per ranked
candidate. The capping, the confidence gating, the explainability all
live in `ranking_feedback_adapter.apply_feedback_to_rank_score`.

Phase 8 entrypoint: `apply_ranking_feedback_fixture`.
Phase 8.5 entrypoint: `apply_ranking_feedback_for_job` (stub).
"""
from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=2048)
def apply_ranking_feedback_fixture(
    job_id: str,
    prior_performance_serialised: dict,
) -> dict:
    """Apply controlled engagement feedback to a job's candidates.

    `prior_performance_serialised` is a dict keyed by stringified
    scene_index → dict containing the PerformanceFeatureView fields the
    feedback adapter needs (engagement_score, engagement_confidence,
    maturity_state, feature_version).
    """
    import uuid as _uuid

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import ClipCandidate, Job, MaturityState, Scene
    from api.services.intel.capability_registry import SceneRecord
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates
    from api.services.intel.ranking_feedback_adapter import PerformanceFeatureView
    from api.services.ranking_snapshot_persistence import persist_ranking_snapshot

    assert engine is not None, "DATABASE_URL must be set for ranking feedback worker"

    with Session(engine) as db:
        job = db.execute(
            select(Job).where(Job.id == _uuid.UUID(job_id))
        ).scalar_one()
        scene_rows = (
            db.execute(select(Scene).where(Scene.job_id == job.id))
            .scalars().all()
        )
        candidate_rows = (
            db.execute(select(ClipCandidate).where(ClipCandidate.job_id == job.id))
            .scalars().all()
        )

        prior: dict[int, PerformanceFeatureView] = {}
        for k, payload in prior_performance_serialised.items():
            prior[int(k)] = PerformanceFeatureView(
                export_id=_uuid.UUID(payload["export_id"]),
                tenant_id=_uuid.UUID(payload["tenant_id"]),
                feature_version=payload.get("feature_version", "v1"),
                maturity_state=MaturityState(payload["maturity_state"]),
                engagement_confidence=float(payload["engagement_confidence"]),
                normalized_view_rate=payload.get("normalized_view_rate"),
                normalized_completion_rate=payload.get("normalized_completion_rate"),
                normalized_watch_time=payload.get("normalized_watch_time"),
                replay_rate=payload.get("replay_rate"),
                share_rate=payload.get("share_rate"),
                engagement_score=float(payload["engagement_score"]),
                experiment_group_id=(
                    _uuid.UUID(payload["experiment_group_id"])
                    if payload.get("experiment_group_id") else None
                ),
            )

        ranked = rank_clip_candidates(
            upload_id=str(job.upload_id),
            scenes=[
                SceneRecord(
                    t_start=s.t_start, t_end=s.t_end, kind=s.kind,
                    arc_position=s.arc_position, intensity=s.intensity,
                    importance=s.importance, signals=s.signals,
                ) for s in scene_rows
            ],
            prior_performance=prior,
        )

        # Snapshot each candidate. Map back from scene_index → candidate row.
        by_scene_index = {i: c for i, c in enumerate(candidate_rows)}
        snapshots = []
        for cand_record in ranked.candidates:
            target = by_scene_index.get(cand_record.scene_index or 0)
            if target is None:
                continue
            snap = persist_ranking_snapshot(
                db, job=job, candidate=target, scores=cand_record.scores,
            )
            snapshots.append({
                "id": str(snap.id),
                "candidate_id": str(snap.candidate_id),
                "base_rank_score": snap.base_rank_score,
                "engagement_adjustment": snap.engagement_adjustment,
                "final_rank_score": snap.final_rank_score,
                "feedback_applied": snap.feedback_applied,
            })
        db.commit()
        return {"snapshots": snapshots, "ranked_count": len(ranked.candidates)}


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=2048)
def apply_ranking_feedback_for_job(job_id: str, tenant_slug: str) -> dict:
    """Phase 8.5 stub — read PerformanceFeatureViews from DB by matching
    scene fingerprints, apply controlled feedback, persist snapshots."""
    raise NotImplementedError(
        "Phase 8.5 — DB-driven PerformanceFeatureView lookup wiring."
    )
